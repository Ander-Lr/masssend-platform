"""Webhooks firmados y rutas de WhatsApp contra PostgreSQL."""

import json
import time
from typing import Any

import pytest
from django.test import Client
from django.utils import timezone

from billing.models import CreditWallet
from mass_sender.models import Contact, Message
from masssend.infrastructure.adapters.mensajeria import whatsapp
from masssend.infrastructure.persistence.envio.models import EnvioFila
from masssend.interfaces.http.webhooks.firma import FirmaInvalida, firmar, verificar
from masssend.interfaces.workers import tareas_envio
from tests.integration.campanas.sesion import Sesion

pytestmark = pytest.mark.django_db
SECRETO = "secreto-de-prueba"
WEBHOOKS = "/api/v1/webhooks/whatsapp/"


@pytest.fixture(autouse=True)
def entorno(settings: Any) -> None:
    settings.WHATSAPP_WEBHOOK_TOKEN = SECRETO
    settings.CANAL_MENSAJERIA = "fake"
    settings.COLA_ENVIOS = "base"
    settings.ALMACEN_ARCHIVOS = "memoria"


def aviso(
    ruta: str, datos: dict[str, Any], secreto: str = SECRETO, desfase: int = 0, **extra: str
) -> Any:
    cuerpo = json.dumps(datos).encode()
    tiempo = str(int(time.time()) + desfase)
    cabeceras = {
        "HTTP_X_MASSSEND_TIEMPO": tiempo,
        "HTTP_X_MASSSEND_FIRMA": firmar(cuerpo, tiempo, secreto),
        **extra,
    }
    return Client().post(WEBHOOKS + ruta, cuerpo, content_type="application/json", **cabeceras)


def test_la_firma_coincide_con_la_del_gateway() -> None:
    """Mismo calculo que index.js: HMAC-SHA256 de "<tiempo>.<cuerpo>"."""
    cuerpo = '{"id": "wa.1", "texto": "Bája ✓"}'.encode()
    firma = firmar(cuerpo, "1762190000", "secreto")
    assert firma.startswith("sha256=") and len(firma) == 71
    verificar(cuerpo, "1762190000", firma, "secreto", 1762190000)
    with pytest.raises(FirmaInvalida):
        verificar(cuerpo + b" ", "1762190000", firma, "secreto", 1762190000)
    with pytest.raises(FirmaInvalida):
        verificar(cuerpo, "ayer", firma, "secreto", 1762190000)


@pytest.mark.parametrize(
    "manipular",
    [
        lambda: Client().post(WEBHOOKS + "mensajes", {}, content_type="application/json"),
        lambda: aviso("mensajes", {"telefono": "593991112222", "texto": "hola"}, "otro"),
        lambda: aviso("mensajes", {"telefono": "593991112222", "texto": "hola"}, desfase=-400),
        lambda: aviso("acuses", {"id_externo": "x", "estado": "leido"}, desfase=400),
        lambda: aviso(
            "resultados",
            {"telefono": "1", "estado": "enviado"},
            HTTP_X_MASSSEND_FIRMA="sha256=" + "0" * 64,
        ),
    ],
)
def test_un_aviso_sin_firma_valida_responde_401(manipular: Any) -> None:
    respuesta = manipular()
    assert respuesta.status_code == 401
    assert respuesta["Content-Type"] == "application/problem+json"
    assert not Message.objects.exists()


def test_sin_secreto_configurado_se_rechaza_todo(settings: Any) -> None:
    settings.WHATSAPP_WEBHOOK_TOKEN = ""
    assert aviso("mensajes", {"telefono": "593991112222", "texto": "hola"}, "").status_code == 401


def test_un_mensaje_entrante_se_registra_una_sola_vez() -> None:
    ana = Sesion("ana")
    Message.objects.create(
        owner=ana.usuario, phone_number="593991112222", direction="outbound", content="Hola"
    )
    datos = {"id": "wa.entrante.1", "telefono": "593991112222", "texto": "Gracias"}
    primero = aviso("mensajes", datos)
    assert primero.status_code == 200
    assert primero.json() == {"repetido": False, "baja": False, "contactos_dados_de_baja": 0}
    assert aviso("mensajes", datos).json()["repetido"] is True
    entrante = Message.objects.get(direction="inbound")
    # Como en el sistema actual: es de quien le escribio por ultima vez.
    assert (entrante.owner, entrante.content) == (ana.usuario, "Gracias")
    assert Contact.objects.filter(owner=ana.usuario, phone_number="593991112222").exists()


def test_baja_da_de_baja_al_numero_en_todas_las_libretas() -> None:
    ana, luis = Sesion("ana"), Sesion("luis")
    ana.crear("0991112222")
    luis.crear("0991112222")
    otro = ana.crear("0993334444")
    respuesta = aviso("mensajes", {"id": "wa.2", "telefono": "593991112222", "texto": " Baja. "})
    # Ana, Luis y el contacto sin dueno que crea el propio mensaje, como en el sistema actual.
    assert respuesta.json() == {"repetido": False, "baja": True, "contactos_dados_de_baja": 3}
    assert Contact.objects.filter(phone_number="593991112222", is_opted_out=False).count() == 0
    assert ana.get("/" + otro["id"]).json()["dado_de_baja"] is False
    # Ya no cuentan como destinatarios de una campana.
    assert ana.crear_campana()["destinatarios"] == 1


def test_un_aviso_mal_formado_responde_422() -> None:
    assert aviso("mensajes", {"telefono": "593991112222"}).status_code == 422
    assert aviso("acuses", {"id_externo": "x", "estado": "visto"}).status_code == 422
    assert (
        aviso("resultados", {"telefono": "1", "estado": "enviado", "envio_id": "abc"}).status_code
        == 422
    )


def lanzar_y_enviar(ana: Sesion, cantidad: int = 1) -> list[EnvioFila]:
    CreditWallet.objects.create(user=ana.usuario, balance=10)
    for i in range(cantidad):
        ana.crear(f"099111111{i}", nombre=f"Cliente {i}")
    campana = ana.crear_campana()
    respuesta = ana.campanas(f"/{campana['id']}/lanzar", "post")
    assert respuesta.status_code == 202
    # La cola publica al confirmar, y aqui la transaccion nunca confirma: se programan a mano.
    EnvioFila.objects.update(programado_para=timezone.now())
    while tareas_envio.procesar_siguiente() is not None:
        pass
    # Con WhatsApp real el id llega despues, en el resultado.
    EnvioFila.objects.update(id_externo=None)
    Message.objects.update(wpp_message_id=None)
    return list(EnvioFila.objects.order_by("orden"))


def test_el_resultado_se_correlaciona_por_envio_id_y_luego_avanzan_los_acuses() -> None:
    ana = Sesion("ana")
    (envio,) = lanzar_y_enviar(ana)
    resultado = {
        "envio_id": str(envio.id),
        "telefono": envio.telefono,
        "estado": "enviado",
        "id_externo": "wamid.ABC",
    }
    assert aviso("resultados", resultado).json() == {"actualizados": 1}
    assert aviso("resultados", resultado).json() == {"actualizados": 0}
    envio.refresh_from_db()
    mensaje = Message.objects.get(pk=envio.mensaje_id)
    assert (envio.id_externo, mensaje.wpp_message_id) == ("wamid.ABC", "wamid.ABC")
    assert aviso("acuses", {"id_externo": "wamid.ABC", "estado": "leido"}).json() == {
        "actualizados": 1
    }
    # Un entregado que llega tarde no deshace el leido.
    assert aviso("acuses", {"id_externo": "wamid.ABC", "estado": "entregado"}).json() == {
        "actualizados": 0
    }
    mensaje.refresh_from_db()
    assert mensaje.delivery_status == "read"


def test_un_rebote_marca_el_envio_y_el_mensaje_como_fallidos() -> None:
    ana = Sesion("ana")
    (envio,) = lanzar_y_enviar(ana)
    datos = {
        "envio_id": str(envio.id),
        "telefono": envio.telefono,
        "estado": "fallido",
        "error": "Bloqueado",
    }
    assert aviso("resultados", datos).json() == {"actualizados": 1}
    assert aviso("resultados", datos).json() == {"actualizados": 0}
    envio.refresh_from_db()
    mensaje = Message.objects.get(pk=envio.mensaje_id)
    assert (envio.estado, mensaje.delivery_status, mensaje.error_log) == (
        "fallido",
        "failed",
        "Bloqueado",
    )


def test_resultados_que_no_corresponden_a_un_envio() -> None:
    ana = Sesion("ana")
    desconocido = {"envio_id": str(ana.public_id), "telefono": "593991112222", "estado": "enviado"}
    assert aviso("resultados", desconocido).json() == {"actualizados": 0}
    # Sin envio_id es un mensaje del chat: se resuelve como antes, por el pendiente mas antiguo.
    Message.objects.create(
        owner=ana.usuario,
        phone_number="593991112222",
        direction="outbound",
        content="Hola",
        delivery_status="pending",
    )
    chat = {"telefono": "593991112222", "estado": "enviado", "id_externo": "wamid.CHAT"}
    assert aviso("resultados", chat).json() == {"actualizados": 1}
    assert Message.objects.get().wpp_message_id == "wamid.CHAT"
    assert aviso("resultados", chat).json() == {"actualizados": 0}


def staff() -> Sesion:
    sesion = Sesion("staff")
    sesion.usuario.is_staff = True
    sesion.usuario.save()
    return sesion


def test_las_rutas_de_whatsapp_son_solo_para_staff() -> None:
    ana = Sesion("ana")
    for metodo, ruta in [("get", "estado"), ("post", "vinculacion"), ("post", "cerrar-sesion")]:
        url = f"/api/v1/whatsapp/{ruta}"
        assert getattr(ana.cliente, metodo)(url).status_code == 403
        assert getattr(Client(), metodo)(url).status_code == 401


def test_whatsapp_con_el_canal_falso() -> None:
    admin = staff()
    assert admin.cliente.get("/api/v1/whatsapp/estado").json() == {
        "conectado": True,
        "codigo_vinculacion": None,
        "qr": None,
    }
    respuesta = admin.cliente.post(
        "/api/v1/whatsapp/vinculacion", {"telefono": "0991112222"}, content_type="application/json"
    )
    assert respuesta.status_code == 409


class Gateway:
    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.llamadas: list[tuple[str, str, Any]] = []
        self.respuestas: dict[str, tuple[int, Any]] = {}
        monkeypatch.setattr(whatsapp.requests, "request", self.request)

    def request(self, metodo: str, url: str, timeout: int = 0, **datos: Any) -> Any:
        ruta = url.split("3001", 1)[1]
        self.llamadas.append((metodo, ruta, datos.get("json")))
        if ruta not in self.respuestas:
            raise whatsapp.requests.ConnectionError()
        estado, cuerpo = self.respuestas[ruta]
        respuesta = whatsapp.requests.Response()
        respuesta.status_code = estado
        respuesta._content = json.dumps(cuerpo).encode()
        return respuesta


def test_whatsapp_contra_el_gateway(monkeypatch: pytest.MonkeyPatch, settings: Any) -> None:
    settings.CANAL_MENSAJERIA = "whatsapp"
    settings.WHATSAPP_API_URL = "http://gateway:3001"
    gateway = Gateway(monkeypatch)
    admin = staff()
    gateway.respuestas["/api/qr"] = (200, {"ready": False, "qr": "2@abc,def", "pairing_code": None})
    assert admin.cliente.get("/api/v1/whatsapp/estado").json() == {
        "conectado": False,
        "codigo_vinculacion": None,
        "qr": "2@abc,def",
    }
    con_codigo = {"ready": False, "qr": "2@viejo", "pairing_code": "XY12-ZW34"}
    gateway.respuestas["/api/qr"] = (200, con_codigo)
    assert admin.cliente.get("/api/v1/whatsapp/estado").json() == {
        "conectado": False,
        "codigo_vinculacion": "XY12-ZW34",
        "qr": None,
    }
    gateway.respuestas["/api/qr"] = (200, {"ready": True, "qr": "2@viejo"})
    assert admin.cliente.get("/api/v1/whatsapp/estado").json()["qr"] is None
    gateway.respuestas["/api/request-pairing"] = (200, {"success": True, "code": "AB12-CD34"})
    respuesta = admin.cliente.post(
        "/api/v1/whatsapp/vinculacion",
        {"telefono": "099 111 2222"},
        content_type="application/json",
    )
    assert respuesta.json()["codigo"] == "AB12-CD34"
    assert gateway.llamadas[-1] == ("POST", "/api/request-pairing", {"phone": "593991112222"})
    gateway.respuestas["/api/request-pairing"] = (400, {"error": "Ya hay un numero conectado."})
    respuesta = admin.cliente.post(
        "/api/v1/whatsapp/vinculacion", {"telefono": "0991112222"}, content_type="application/json"
    )
    assert respuesta.status_code == 409
    gateway.respuestas["/api/logout"] = (200, {"success": True})
    assert admin.cliente.post("/api/v1/whatsapp/cerrar-sesion").status_code == 200
    del gateway.respuestas["/api/qr"]
    assert admin.cliente.get("/api/v1/whatsapp/estado").status_code == 503
