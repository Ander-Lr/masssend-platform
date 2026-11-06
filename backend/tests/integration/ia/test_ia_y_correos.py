"""Asistente, notificaciones, cola y trabajador contra PostgreSQL."""

import base64
import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework_simplejwt.tokens import AccessToken

from email_auth.models import EmailTask, QueueControl
from masssend.application.ia.puertos import MensajeChat
from masssend.domain.identidad.notificacion import CABECERA_PDF
from masssend.domain.shared.errores import ServicioNoDisponible
from masssend.infrastructure.adapters.ia.ollama import GeneradorOllama
from masssend.infrastructure.composition.root import contenedor
from masssend.infrastructure.persistence.identidad.models import CuentaIdentidad
from masssend.interfaces.workers.tareas_correo import procesar_pendientes

pytestmark = pytest.mark.django_db
Usuario = get_user_model()
REDACTA = {"pregunta": "Redacta un mensaje para mi tienda"}
NOTA = {"destinatario": "luis@prueba.local", "asunto": "A", "titulo": "T", "mensaje": "M"}


@pytest.fixture(autouse=True)
def generador_falso(settings: Any) -> None:
    settings.GENERADOR_TEXTO = "fake"
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.EMAIL_HOST_USER = "masssend@prueba.local"


def cabecera(staff: bool = False, nombre: str = "ana") -> dict[str, str]:
    usuario = Usuario.objects.create_user(f"{nombre}@prueba.local", is_staff=staff)
    public_id = contenedor.generador_ids().nuevo()
    CuentaIdentidad.objects.create(usuario=usuario, public_id=public_id)
    token = AccessToken.for_user(usuario)
    token["public_id"] = str(public_id)
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


def post_json(client: Client, ruta: str, datos: Any, auth: dict[str, str]) -> Any:
    return client.post(
        f"/api/v1/{ruta}", json.dumps(datos), content_type="application/json", **auth
    )


def test_el_asistente_responde_con_el_generador_falso(client: Client) -> None:
    respuesta = post_json(
        client, "asistente/mensajes", {"pregunta": "Redacta un mensaje para mi tienda"}, cabecera()
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["modelo"] == "generador-falso"


def test_el_asistente_responde_el_saldo_real_de_la_cuenta(client: Client) -> None:
    respuesta = post_json(
        client, "asistente/mensajes", {"pregunta": "¿Cuántos créditos tengo?"}, cabecera()
    )
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["modelo"] == "Tu cuenta"
    assert datos["respuesta"].startswith("Tienes ")
    assert "créditos disponibles" in datos["respuesta"]


def test_una_pregunta_ajena_no_llega_al_modelo(client: Client, settings: Any) -> None:
    settings.GENERADOR_TEXTO = "ollama"
    ruta = "masssend.infrastructure.adapters.ia.ollama.requests.post"
    with patch(ruta) as llamada:
        respuesta = post_json(
            client, "asistente/mensajes", {"pregunta": "¿Cuál es la capital de Roma?"}, cabecera()
        )
    assert respuesta.status_code == 200
    assert respuesta.json()["respuesta"].startswith("Solo puedo ayudarte con el uso de MassSend")
    llamada.assert_not_called()


@pytest.mark.parametrize(
    "datos",
    [
        {"pregunta": "  "},
        {"pregunta": "x" * 2001},
        {},
        {"pregunta": "hola", "historial": [{"rol": "system", "contenido": "x"}]},
    ],
)
def test_el_asistente_valida(client: Client, datos: dict[str, Any]) -> None:
    respuesta = post_json(client, "asistente/mensajes", datos, cabecera())
    assert respuesta.status_code == 422


def test_el_asistente_exige_sesion(client: Client) -> None:
    assert post_json(client, "asistente/mensajes", {"pregunta": "x"}, {}).status_code == 401
    assert client.get("/api/v1/asistente/salud").status_code == 401


def test_si_ollama_cae_responde_503(client: Client, settings: Any) -> None:
    settings.GENERADOR_TEXTO = "ollama"
    auth = cabecera()
    ruta = "masssend.infrastructure.adapters.ia.ollama.requests.post"
    with patch(ruta, side_effect=requests.ConnectionError("detalle-interno")):
        respuesta = post_json(client, "asistente/mensajes", REDACTA, auth)
    assert respuesta.status_code == 503
    assert b"detalle-interno" not in respuesta.content


def test_si_ollama_tarda_responde_503(client: Client, settings: Any) -> None:
    settings.GENERADOR_TEXTO = "ollama"
    auth = cabecera()
    ruta = "masssend.infrastructure.adapters.ia.ollama.requests.post"
    with patch(ruta, side_effect=requests.Timeout):
        respuesta = post_json(client, "asistente/mensajes", REDACTA, auth)
    assert respuesta.status_code == 503


def test_ollama_envia_los_mensajes_por_chat_y_lee_la_respuesta() -> None:
    simulada = MagicMock()
    simulada.json.return_value = {
        "message": {"role": "assistant", "content": " hola "},
        "model": "m",
    }
    ruta = "masssend.infrastructure.adapters.ia.ollama.requests.post"
    mensajes = [MensajeChat("system", "contexto"), MensajeChat("user", "pregunta")]
    with patch(ruta, return_value=simulada) as llamada:
        generado = GeneradorOllama("http://ollama/", "m", 5).generar(mensajes)
    assert (generado.texto, generado.modelo) == (" hola ", "m")
    assert llamada.call_args.args[0] == "http://ollama/api/chat"
    cuerpo = llamada.call_args.kwargs["json"]
    assert cuerpo["messages"] == [
        {"role": "system", "content": "contexto"},
        {"role": "user", "content": "pregunta"},
    ]
    assert cuerpo["stream"] is False
    assert cuerpo["options"]["repeat_penalty"] > 1
    assert llamada.call_args.kwargs["timeout"] == 5
    assert generado.completo is True


def test_ollama_avisa_cuando_corta_la_respuesta_por_largo() -> None:
    simulada = MagicMock()
    simulada.json.return_value = {
        "message": {"role": "assistant", "content": "1. Paso.\n2. Aseg"},
        "model": "m",
        "done_reason": "length",
    }
    ruta = "masssend.infrastructure.adapters.ia.ollama.requests.post"
    with patch(ruta, return_value=simulada):
        generado = GeneradorOllama("http://ollama/", "m", 5).generar([MensajeChat("user", "x")])
    assert generado.completo is False


@pytest.mark.parametrize(
    "cuerpo",
    [{"error": "prediction aborted, token repeat limit reached"}, {"message": None}, []],
    ids=["sin-mensaje", "mensaje-nulo", "no-es-objeto"],
)
def test_ollama_con_respuesta_rara_responde_no_disponible(cuerpo: Any) -> None:
    simulada = MagicMock()
    simulada.json.return_value = cuerpo
    ruta = "masssend.infrastructure.adapters.ia.ollama.requests.post"
    with patch(ruta, return_value=simulada), pytest.raises(ServicioNoDisponible):
        GeneradorOllama("http://ollama", "m", 5).generar([MensajeChat("user", "x")])


def test_ollama_distingue_el_modelo_exacto() -> None:
    simulada = MagicMock()
    simulada.json.return_value = {"models": [{"name": "qwen2.5:1b"}]}
    ruta = "masssend.infrastructure.adapters.ia.ollama.requests.get"
    with patch(ruta, return_value=simulada):
        estado = GeneradorOllama("http://ollama", "qwen2.5:0.5b", 5).estado()
    assert estado.disponible
    assert not estado.modelo_descargado


def test_ollama_apagado_se_informa_sin_fallar() -> None:
    ruta = "masssend.infrastructure.adapters.ia.ollama.requests.get"
    with patch(ruta, side_effect=requests.ConnectionError):
        estado = GeneradorOllama("http://ollama", "m", 5).estado()
    assert not estado.disponible


def test_con_ollama_caido_no_se_lanza_en_generar() -> None:
    ruta = "masssend.infrastructure.adapters.ia.ollama.requests.post"
    with patch(ruta, side_effect=requests.ConnectionError), pytest.raises(ServicioNoDisponible):
        GeneradorOllama("http://ollama", "m", 5).generar([MensajeChat("user", "x")])


def test_staff_encola_y_el_trabajador_envia(client: Client) -> None:
    respuesta = post_json(client, "notificaciones", NOTA, cabecera(staff=True))
    assert respuesta.status_code == 202
    tarea = EmailTask.objects.get(pk=respuesta.json()["tarea_id"])
    assert tarea.task_type == EmailTask.TYPE_CUSTOM_NOTIFICATION
    assert tarea.status == EmailTask.STATUS_PENDING
    assert mail.outbox == []
    assert procesar_pendientes() == 1
    tarea.refresh_from_db()
    assert tarea.status == EmailTask.STATUS_SENT
    assert mail.outbox[0].to == ["luis@prueba.local"]


def test_un_usuario_normal_no_envia_correos(client: Client) -> None:
    assert post_json(client, "notificaciones", NOTA, cabecera()).status_code == 403
    assert not EmailTask.objects.exists()


def test_el_adjunto_llega_intacto(client: Client) -> None:
    contenido = CABECERA_PDF + b"contenido"
    archivo = SimpleUploadedFile("nota.pdf", contenido, content_type="application/pdf")
    respuesta = client.post(
        "/api/v1/notificaciones", {**NOTA, "archivo": archivo}, **cabecera(staff=True)
    )
    assert respuesta.status_code == 202
    tarea = EmailTask.objects.get()
    assert tarea.task_type == EmailTask.TYPE_ATTACHMENT_NOTIFICATION
    assert base64.b64decode(tarea.payload["attachment"]["contentBase64"]) == contenido
    procesar_pendientes()
    assert mail.outbox[0].attachments[0][:2] == ("nota.pdf", contenido)


@pytest.mark.parametrize(
    ("nombre", "tipo", "contenido"),
    [
        ("a.pdf", "application/pdf", b"MZ\x90"),
        ("a.exe", "application/x-msdownload", b"MZ\x90"),
    ],
)
def test_rechaza_adjuntos_peligrosos(
    client: Client, nombre: str, tipo: str, contenido: bytes
) -> None:
    archivo = SimpleUploadedFile(nombre, contenido, content_type=tipo)
    respuesta = client.post(
        "/api/v1/notificaciones", {**NOTA, "archivo": archivo}, **cabecera(staff=True)
    )
    assert respuesta.status_code == 422
    assert respuesta.json()["campo"] == "archivo"
    assert not EmailTask.objects.exists()


def test_respeta_el_tamano_maximo(client: Client, settings: Any) -> None:
    settings.EMAIL_MAX_ATTACHMENT_SIZE_MB = 1
    archivo = SimpleUploadedFile(
        "a.pdf", CABECERA_PDF + b"0" * 1024 * 1024, content_type="application/pdf"
    )
    respuesta = client.post(
        "/api/v1/notificaciones", {**NOTA, "archivo": archivo}, **cabecera(staff=True)
    )
    assert respuesta.status_code == 422


def test_rechaza_inyeccion_de_cabeceras(client: Client) -> None:
    datos = {**NOTA, "asunto": "Hola\nBcc: otro@prueba.local"}
    respuesta = post_json(client, "notificaciones", datos, cabecera(staff=True))
    assert respuesta.status_code == 422
    assert respuesta.json()["campo"] == "asunto"


def test_el_listado_nunca_expone_el_contenido(client: Client) -> None:
    EmailTask.objects.create(
        task_type=EmailTask.TYPE_ACCOUNT_VERIFICATION,
        recipient="ana@prueba.local",
        subject="Código",
        payload={"code": "987654"},
    )
    respuesta = client.get("/api/v1/cola-correos/tareas", **cabecera(staff=True))
    assert respuesta.status_code == 200
    assert b"987654" not in respuesta.content
    assert b"payload" not in respuesta.content
    assert respuesta.json()["pausada"] is False


def test_el_listado_recorre_todo_por_cursor(client: Client) -> None:
    for numero in range(5):
        EmailTask.objects.create(
            task_type=EmailTask.TYPE_CUSTOM_NOTIFICATION,
            recipient="a@prueba.local",
            subject=str(numero),
        )
    auth = cabecera(staff=True)
    asuntos: list[str] = []
    cursor = None
    for _ in range(6):
        parametros = {"limite": 2, **({"cursor": cursor} if cursor else {})}
        pagina = client.get("/api/v1/cola-correos/tareas", parametros, **auth).json()
        asuntos.extend(t["asunto"] for t in pagina["datos"])
        cursor = pagina["pagina"]["siguiente_cursor"]
        if cursor is None:
            break
    assert asuntos == ["4", "3", "2", "1", "0"]


def test_el_listado_no_carga_el_contenido_en_la_consulta(client: Client) -> None:
    EmailTask.objects.create(
        task_type=EmailTask.TYPE_CUSTOM_NOTIFICATION, recipient="a@prueba.local", subject="s"
    )
    auth = cabecera(staff=True)
    with CaptureQueriesContext(connection) as consultas:
        client.get("/api/v1/cola-correos/tareas", **auth)
    tablas = [c["sql"] for c in consultas if "email_auth_email_task" in c["sql"]]
    assert tablas
    assert all('"payload"' not in sql for sql in tablas)


@pytest.mark.parametrize("ruta", ["pausar", "reanudar"])
def test_solo_staff_controla_la_cola(client: Client, ruta: str) -> None:
    assert post_json(client, f"cola-correos/{ruta}", {}, cabecera()).status_code == 403


def test_con_la_cola_pausada_el_trabajador_no_envia(client: Client) -> None:
    auth = cabecera(staff=True)
    post_json(client, "cola-correos/pausar", {}, auth)
    post_json(client, "notificaciones", NOTA, auth)
    assert QueueControl.get_solo().paused
    assert procesar_pendientes() == 0
    assert client.get("/api/v1/cola-correos/tareas", **auth).json()["pausada"] is True
    post_json(client, "cola-correos/reanudar", {}, auth)
    assert procesar_pendientes() == 1


def test_un_fallo_de_envio_reintenta_sin_tumbar_el_trabajador(client: Client) -> None:
    post_json(client, "notificaciones", NOTA, cabecera(staff=True))
    ruta = "email_auth.services.email_sender.DjangoSmtpEmailSender.send_email"
    with patch(ruta, side_effect=OSError("smtp caido")):
        assert procesar_pendientes(maximo=1) == 1
    tarea = EmailTask.objects.get()
    assert (tarea.status, tarea.attempts) == (EmailTask.STATUS_PENDING, 1)


@pytest.mark.parametrize(
    ("metodo", "ruta"),
    [
        ("post", "asistente/mensajes"),
        ("get", "asistente/salud"),
        ("post", "notificaciones"),
        ("get", "cola-correos/tareas"),
        ("post", "cola-correos/pausar"),
        ("post", "cola-correos/reanudar"),
    ],
)
def test_un_jwt_del_sistema_actual_no_entra(client: Client, metodo: str, ruta: str) -> None:
    usuario = Usuario.objects.create_user("admin@prueba.local", is_staff=True)
    token = {"HTTP_AUTHORIZATION": f"Bearer {AccessToken.for_user(usuario)}"}
    if metodo == "get":
        respuesta = client.get(f"/api/v1/{ruta}", **token)
    else:
        respuesta = post_json(client, ruta, {**NOTA, "pregunta": "hola"}, token)
    assert respuesta.status_code == 401
    assert respuesta["Content-Type"] == "application/problem+json"
    assert not EmailTask.objects.exists()
    assert not QueueControl.get_solo().paused


def test_el_listado_con_la_misma_fecha_no_pierde_ni_repite(client: Client) -> None:
    for numero in range(5):
        EmailTask.objects.create(
            task_type=EmailTask.TYPE_CUSTOM_NOTIFICATION,
            recipient="a@prueba.local",
            subject=str(numero),
        )
    EmailTask.objects.update(created_at=timezone.now())
    auth = cabecera(staff=True)
    asuntos: list[str] = []
    cursor = None
    for _ in range(6):
        parametros = {"limite": 2, **({"cursor": cursor} if cursor else {})}
        pagina = client.get("/api/v1/cola-correos/tareas", parametros, **auth).json()
        asuntos.extend(t["asunto"] for t in pagina["datos"])
        cursor = pagina["pagina"]["siguiente_cursor"]
        if cursor is None:
            break
    assert sorted(asuntos) == list("01234")


def test_el_trabajador_respeta_el_maximo_por_ciclo(client: Client) -> None:
    auth = cabecera(staff=True)
    for _ in range(3):
        post_json(client, "notificaciones", NOTA, auth)
    assert procesar_pendientes(maximo=2) == 2
    assert EmailTask.objects.filter(status=EmailTask.STATUS_PENDING).count() == 1
