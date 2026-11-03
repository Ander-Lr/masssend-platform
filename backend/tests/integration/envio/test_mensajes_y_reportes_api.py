"""Mensajes, conversaciones, chat y reportes contra PostgreSQL, con su costo en consultas."""

import json
import time
from datetime import timedelta
from typing import Any

import pytest
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from mass_sender.models import Campaign, Message
from masssend.application.envio.consultas import FiltroMensajes
from masssend.domain.shared.paginacion import PeticionPagina
from masssend.infrastructure.adapters.mensajeria import whatsapp
from masssend.infrastructure.composition.envio import contenedor_envio
from masssend.infrastructure.persistence.envio.models import EnvioFila, MensajeFila
from masssend.interfaces.http.webhooks.firma import firmar
from tests.integration.campanas.sesion import Sesion

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def entorno(settings: Any) -> None:
    settings.CANAL_MENSAJERIA = "fake"
    settings.WHATSAPP_WEBHOOK_TOKEN = "secreto"


def mensaje(sesion: Sesion, telefono: str, texto: str, **datos: Any) -> Message:
    return Message.objects.create(
        owner=sesion.usuario,
        phone_number=telefono,
        content=texto,
        direction=datos.pop("direction", "outbound"),
        delivery_status=datos.pop("delivery_status", "sent"),
        **datos,
    )


def public_id(fila: Message) -> str:
    return str(MensajeFila.objects.get(pk=fila.pk).public_id)


def staff() -> Sesion:
    sesion = Sesion("staff")
    sesion.usuario.is_staff = True
    sesion.usuario.save()
    return sesion


def get(sesion: Sesion, ruta: str, **params: Any) -> Any:
    return sesion.cliente.get("/api/v1/" + ruta, params)


def post(sesion: Sesion, ruta: str, datos: Any) -> Any:
    return sesion.cliente.post("/api/v1/" + ruta, datos, content_type="application/json")


def test_mensajes_propios_con_nombre_y_campana() -> None:
    ana, luis = Sesion("ana"), Sesion("luis")
    ana.crear("0991112222", nombre="Pedro")
    campana = Campaign.objects.create(owner=ana.usuario, name="Promo", message_template="Hola")
    mensaje(ana, "593991112222", "Hola Pedro", campaign=campana, delivery_status="read")
    mensaje(ana, "593991112222", "Gracias", direction="inbound", delivery_status="pending")
    mensaje(ana, "120363@g.us", "Grupo")
    mensaje(luis, "593993334444", "De Luis")
    datos = get(ana, "mensajes").json()["datos"]
    assert [m["texto"] for m in datos] == ["Gracias", "Hola Pedro"]
    saliente = datos[1]
    assert (saliente["nombre"], saliente["campana"], saliente["estado"]) == (
        "Pedro",
        "Promo",
        "leido",
    )
    assert saliente["direccion"] == "saliente" and saliente["campana_id"]
    assert get(luis, "mensajes").json()["datos"][0]["texto"] == "De Luis"


def test_filtros_y_paginacion_de_mensajes() -> None:
    ana = Sesion("ana")
    for i in range(5):
        mensaje(
            ana, f"59399111111{i}", f"Mensaje {i}", delivery_status="failed" if i == 2 else "sent"
        )
    assert [m["texto"] for m in get(ana, "mensajes", estado="fallido").json()["datos"]] == [
        "Mensaje 2"
    ]
    assert len(get(ana, "mensajes", direccion="entrante").json()["datos"]) == 0
    assert [m["texto"] for m in get(ana, "mensajes", telefono="0991111113").json()["datos"]] == [
        "Mensaje 3"
    ]
    assert [m["texto"] for m in get(ana, "mensajes", texto="aje 4").json()["datos"]] == [
        "Mensaje 4"
    ]
    primera = get(ana, "mensajes", limite=3).json()
    segunda = get(ana, "mensajes", limite=3, cursor=primera["pagina"]["siguiente_cursor"]).json()
    textos = [m["texto"] for m in primera["datos"] + segunda["datos"]]
    assert textos == [f"Mensaje {i}" for i in range(4, -1, -1)]
    assert not segunda["pagina"]["tiene_mas"]
    for clave, valor in [("estado", "visto"), ("direccion", "arriba"), ("cursor", "abc")]:
        respuesta = get(ana, "mensajes", **{clave: valor})
        assert (respuesta.status_code, respuesta.json()["campo"]) == (422, clave)


def test_listar_mensajes_cuesta_dos_consultas() -> None:
    ana = Sesion("ana")
    for i in range(30):
        numero = f"5939911111{i:02d}"
        ana.crear(numero, nombre=f"C{i}")
        mensaje(ana, numero, f"Hola {i}")
    with CaptureQueriesContext(connection) as consultas:
        pagina = contenedor_envio.listar_mensajes().ejecutar(
            ana.public_id, FiltroMensajes(), PeticionPagina(limite=20)
        )
    assert len(pagina.elementos) == 20
    assert {m.nombre for m in pagina.elementos} <= {f"C{i}" for i in range(30)}
    assert len(consultas) == 2


def test_eliminar_mensajes_solo_los_propios() -> None:
    ana, luis = Sesion("ana"), Sesion("luis")
    propios = [mensaje(ana, "593991112222", f"Hola {i}") for i in range(2)]
    ajeno = mensaje(luis, "593993334444", "De Luis")
    respuesta = post(
        ana, "mensajes/eliminar-lote", {"ids": [*map(public_id, propios), public_id(ajeno)]}
    )
    assert respuesta.json() == {"eliminados": 2}
    assert list(Message.objects.values_list("content", flat=True)) == ["De Luis"]
    assert post(ana, "mensajes/eliminar-lote", {"ids": []}).status_code == 422
    assert post(ana, "mensajes/eliminar-lote", {"ids": ["abc"]}).status_code == 422


def test_eliminar_un_mensaje_de_campana_conserva_el_envio() -> None:
    ana = Sesion("ana")
    fila = mensaje(ana, "593991112222", "Hola")
    envio = EnvioFila.objects.create(
        id=ana.public_id,
        campana_id=ana.public_id,
        owner_id=ana.public_id,
        contacto_id=ana.public_id,
        telefono="593991112222",
        orden=0,
        estado="enviado",
        mensaje=fila,
    )
    assert post(ana, "mensajes/eliminar-lote", {"ids": [public_id(fila)]}).json() == {
        "eliminados": 1
    }
    envio.refresh_from_db()
    assert envio.mensaje_id is None


def test_conversaciones_solo_staff_y_la_mas_reciente_primero() -> None:
    ana = Sesion("ana")
    admin = staff()
    ana.crear("0991112222", nombre="Pedro")
    viejo = mensaje(ana, "593991112222", "Hola Pedro")
    Message.objects.filter(pk=viejo.pk).update(sent_at=timezone.now() - timedelta(hours=2))
    mensaje(ana, "593991112222", "¿Llegó?", direction="inbound")
    mensaje(ana, "593993334444", "Hola Maria")
    Message.objects.filter(content="Hola Maria").update(sent_at=timezone.now() - timedelta(hours=1))
    assert get(ana, "conversaciones").status_code == 403
    assert Client().get("/api/v1/conversaciones").status_code == 401
    datos = get(admin, "conversaciones").json()["datos"]
    assert [(c["telefono"], c["nombre"], c["mensajes"]) for c in datos] == [
        ("593991112222", "Pedro", 2),
        ("593993334444", "593993334444", 1),
    ]
    assert (datos[0]["ultimo_texto"], datos[0]["ultima_direccion"]) == ("¿Llegó?", "entrante")
    primera = get(admin, "conversaciones", limite=1).json()
    segunda = get(
        admin, "conversaciones", limite=1, cursor=primera["pagina"]["siguiente_cursor"]
    ).json()
    assert [c["telefono"] for c in primera["datos"] + segunda["datos"]] == [
        "593991112222",
        "593993334444",
    ]
    assert not segunda["pagina"]["tiene_mas"]


def test_listar_conversaciones_cuesta_tres_consultas() -> None:
    ana = Sesion("ana")
    for i in range(25):
        for texto in ("Hola", "Respuesta"):
            mensaje(ana, f"5939922222{i:02d}", texto)
    with CaptureQueriesContext(connection) as consultas:
        pagina = contenedor_envio.listar_conversaciones().ejecutar(PeticionPagina(limite=20))
    assert len(pagina.elementos) == 20 and pagina.tiene_mas
    assert len(consultas) == 3


def test_el_chat_envia_con_el_canal_falso() -> None:
    admin = staff()
    respuesta = post(
        admin, "conversaciones/099 111 2222/mensajes", {"texto": "Hola desde el panel"}
    )
    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert (cuerpo["telefono"], cuerpo["estado"]) == ("593991112222", "enviado")
    fila = MensajeFila.objects.get(public_id=cuerpo["id"])
    assert (fila.delivery_status, fila.wpp_message_id) == ("sent", f"falso-{cuerpo['id']}")
    assert get(admin, "conversaciones").json()["datos"][0]["ultimo_texto"] == "Hola desde el panel"


def test_el_chat_valida_y_es_solo_staff() -> None:
    admin, ana = staff(), Sesion("ana")
    assert post(ana, "conversaciones/0991112222/mensajes", {"texto": "Hola"}).status_code == 403
    respuesta = post(admin, "conversaciones/022345678/mensajes", {"texto": "Hola"})
    assert (respuesta.status_code, respuesta.json()["campo"]) == (422, "telefono")
    respuesta = post(admin, "conversaciones/0991112222/mensajes", {"texto": "  "})
    assert (respuesta.status_code, respuesta.json()["campo"]) == (422, "texto")
    # Un numero sin WhatsApp no es un error de la peticion: queda registrado como fallido.
    rechazado = post(admin, "conversaciones/593990000000/mensajes", {"texto": "Hola"})
    assert rechazado.status_code == 201
    assert (rechazado.json()["estado"], rechazado.json()["detalle"]) == (
        "fallido",
        "El número no tiene WhatsApp.",
    )


def test_el_chat_con_whatsapp_real_espera_el_webhook(
    monkeypatch: pytest.MonkeyPatch, settings: Any
) -> None:
    settings.CANAL_MENSAJERIA = "whatsapp"
    settings.WHATSAPP_API_URL = "http://gateway:3001"
    enviados: list[Any] = []

    def falso_post(url: str, json: Any = None, timeout: int = 0) -> Any:
        enviados.append(json)
        respuesta = whatsapp.requests.Response()
        respuesta.status_code = 200
        respuesta._content = b'{"success": true, "status": "queued"}'
        return respuesta

    monkeypatch.setattr(whatsapp.requests, "post", falso_post)
    admin = staff()
    cuerpo = post(admin, "conversaciones/0991112222/mensajes", {"texto": "Hola"}).json()
    assert cuerpo["estado"] == "pendiente"
    assert enviados[0]["envio_id"] == cuerpo["id"]
    # El gateway devuelve el mismo id con el resultado.
    datos = {
        "envio_id": cuerpo["id"],
        "telefono": "593991112222",
        "estado": "enviado",
        "id_externo": "wamid.X",
    }
    crudo = json.dumps(datos).encode()
    tiempo = str(int(time.time()))
    respuesta = Client().post(
        "/api/v1/webhooks/whatsapp/resultados",
        crudo,
        content_type="application/json",
        HTTP_X_MASSSEND_TIEMPO=tiempo,
        HTTP_X_MASSSEND_FIRMA=firmar(crudo, tiempo, "secreto"),
    )
    assert respuesta.json() == {"actualizados": 1}
    fila = MensajeFila.objects.get(public_id=cuerpo["id"])
    assert (fila.delivery_status, fila.wpp_message_id) == ("sent", "wamid.X")


def test_el_chat_sin_gateway_responde_503_y_queda_fallido(settings: Any) -> None:
    settings.CANAL_MENSAJERIA = "whatsapp"
    settings.WHATSAPP_API_URL = "http://127.0.0.1:9"
    admin = staff()
    assert post(admin, "conversaciones/0991112222/mensajes", {"texto": "Hola"}).status_code == 503
    assert MensajeFila.objects.get().delivery_status == "failed"


def test_reporte_del_periodo() -> None:
    ana, luis = Sesion("ana"), Sesion("luis")
    ana.crear("0991112222")
    baja = ana.crear("0993334444")
    ana.patch("/" + baja["id"], {"dado_de_baja": True})
    for estado in ["sent", "delivered", "delivered", "read", "failed", "pending"]:
        mensaje(ana, "593991112222", "Hola", delivery_status=estado)
    mensaje(ana, "593991112222", "Gracias", direction="inbound")
    viejo = mensaje(ana, "593991112222", "Hace dos meses")
    Message.objects.filter(pk=viejo.pk).update(sent_at=timezone.now() - timedelta(days=60))
    mensaje(luis, "593993334444", "De Luis")
    Campaign.objects.create(owner=ana.usuario, name="A", message_template="x", status="completed")
    Campaign.objects.create(owner=ana.usuario, name="B", message_template="x", status="scheduled")
    Campaign.objects.create(owner=ana.usuario, name="C", message_template="x")
    reporte = get(ana, "reportes").json()
    assert reporte["resumen"] == {
        "enviados": 6,
        "recibidos": 1,
        "entregados": 2,
        "leidos": 1,
        "fallidos": 1,
        "pendientes": 1,
        "tasa_entrega": 75.0,
        "tasa_lectura": 25.0,
    }
    hoy = timezone.localdate().isoformat()
    assert reporte["por_dia"] == [{"dia": hoy, "enviados": 6, "recibidos": 1}]
    assert reporte["campanas"] == {"completada": 1, "en_curso": 1, "borrador": 1}
    assert reporte["contactos"] == {"total": 2, "dados_de_baja": 1}
    antes = (timezone.localdate() - timedelta(days=90)).isoformat()
    historico = get(ana, "reportes", desde=antes).json()
    assert historico["resumen"]["enviados"] == 7


@pytest.mark.parametrize(
    ("params", "campo"),
    [({"desde": "2026-02-01", "hasta": "2026-01-01"}, "desde"), ({"hasta": "ayer"}, "hasta")],
)
def test_un_periodo_invalido_responde_422(params: dict[str, str], campo: str) -> None:
    respuesta = get(Sesion("ana"), "reportes", **params)
    assert (respuesta.status_code, respuesta.json()["campo"]) == (422, campo)
