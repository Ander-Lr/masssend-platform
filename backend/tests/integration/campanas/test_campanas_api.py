"""Campanas contra PostgreSQL: estados, aislamiento, destinatarios y adjuntos."""

from typing import Any

import pytest
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from mass_sender.models import Campaign, CampaignProgress, Contact, Message
from masssend.domain.campanas.repositorios import FiltroCampanas
from masssend.domain.shared.identificadores import id_publico
from masssend.domain.shared.paginacion import PeticionPagina
from masssend.infrastructure.composition.campanas import contenedor_campanas
from masssend.infrastructure.persistence.campanas.models import CampanaFila
from tests.integration.campanas.sesion import Sesion

pytestmark = pytest.mark.django_db

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"0" * 64


@pytest.fixture(autouse=True)
def almacen_en_memoria(settings: Any) -> None:
    settings.ALMACEN_ARCHIVOS = "memoria"


@pytest.fixture
def ana() -> Sesion:
    return Sesion("ana")


@pytest.fixture
def luis() -> Sesion:
    return Sesion("luis")


def legacy(campana: dict[str, Any]) -> Campaign:
    return Campaign.objects.get(pk=CampanaFila.objects.get(public_id=campana["id"]).pk)


def poner_estado(campana: dict[str, Any], estado_db: str) -> None:
    Campaign.objects.filter(pk=legacy(campana).pk).update(status=estado_db)


def test_crear_un_borrador_con_sus_destinatarios(ana: Sesion, luis: Sesion) -> None:
    ana.crear("0991111111", etiquetas="vip")
    ana.crear("0992222222", etiquetas="vip-antiguo")
    ana.crear("0993333333", etiquetas="lead, vip")
    baja = ana.crear("0994444444", etiquetas="vip")
    ana.patch("/" + baja["id"], {"dado_de_baja": True})
    luis.crear("0995555555", etiquetas="vip")
    campana = ana.crear_campana(nombre=" Promo ", etiquetas=["vip"])
    assert id_publico(campana["id"])
    assert (campana["nombre"], campana["estado"], campana["etiquetas"]) == (
        "Promo",
        "borrador",
        ["vip"],
    )
    # La etiqueta debe coincidir completa, sin bajas ni contactos ajenos.
    assert campana["destinatarios"] == 2
    assert campana["tiene_adjunto"] is False
    fila = legacy(campana)
    assert (fila.owner, fila.status, fila.target_tags) == (ana.usuario, "draft", "vip")


def test_sin_etiquetas_llega_a_todos_menos_las_bajas_y_los_grupos(ana: Sesion) -> None:
    ana.crear("0991111111")
    Contact.objects.create(owner=ana.usuario, phone_number="123456@g.us")
    Contact.objects.create(owner=ana.usuario, phone_number="593990000000", is_opted_out=True)
    assert ana.crear_campana()["destinatarios"] == 1


@pytest.mark.parametrize(
    ("cuerpo", "campo"),
    [
        ({"nombre": "", "mensaje": "Hola"}, "nombre"),
        ({"nombre": "Promo", "mensaje": " "}, "mensaje"),
    ],
)
def test_datos_invalidos_responden_422(ana: Sesion, cuerpo: dict[str, str], campo: str) -> None:
    respuesta = ana.campanas(metodo="post", datos=cuerpo)
    assert respuesta.status_code == 422
    assert respuesta.json()["campo"] == campo
    assert not Campaign.objects.exists()


def test_sin_token_responde_401() -> None:
    assert Client().get("/api/v1/campanas").status_code == 401


def test_una_campana_ajena_responde_404(ana: Sesion, luis: Sesion) -> None:
    campana = ana.crear_campana()
    ruta = "/" + campana["id"]
    assert luis.campanas(ruta).status_code == 404
    assert luis.campanas(ruta, "patch", {"nombre": "Robada"}).status_code == 404
    assert luis.campanas(ruta, "delete").status_code == 404
    assert luis.subir(campana["id"], "promo.png", PNG).status_code == 404
    assert luis.campanas(ruta + "/adjunto").status_code == 404
    assert luis.campanas().json()["datos"] == []
    assert legacy(campana).name == "Promo"


def test_un_id_mal_formado_responde_404(ana: Sesion) -> None:
    assert ana.campanas("/no-es-un-id").status_code == 404


def test_editar_un_borrador(ana: Sesion) -> None:
    ana.crear("0991111111", etiquetas="lead")
    campana = ana.crear_campana(etiquetas="vip")
    respuesta = ana.campanas(
        "/" + campana["id"], "patch", {"etiquetas": ["lead"], "mensaje": "Hola"}
    )
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert (cuerpo["nombre"], cuerpo["mensaje"], cuerpo["destinatarios"]) == ("Promo", "Hola", 1)


@pytest.mark.parametrize(
    ("estado_db", "estado"),
    [
        ("running", "en_curso"),
        ("scheduled", "en_curso"),
        ("completed", "completada"),
        ("cancelled", "cancelada"),
    ],
)
def test_solo_un_borrador_se_modifica(ana: Sesion, estado_db: str, estado: str) -> None:
    campana = ana.crear_campana()
    poner_estado(campana, estado_db)
    ruta = "/" + campana["id"]
    assert ana.campanas(ruta).json()["estado"] == estado
    respuesta = ana.campanas(ruta, "patch", {"nombre": "Otra"})
    assert respuesta.status_code == 409
    assert respuesta.json()["codigo"] == "estado_invalido"
    assert ana.subir(campana["id"], "promo.png", PNG).status_code == 409
    assert legacy(campana).name == "Promo"


def test_eliminar_borra_tambien_progreso_y_mensajes(ana: Sesion) -> None:
    campana = ana.crear_campana()
    fila = legacy(campana)
    CampaignProgress.objects.create(campaign=fila, total=1)
    Message.objects.create(
        owner=ana.usuario,
        campaign=fila,
        phone_number="593991111111",
        direction="outbound",
        content="Hola",
    )
    assert ana.campanas("/" + campana["id"], "delete").status_code == 204
    assert not Campaign.objects.exists()
    assert not Message.objects.exists()
    assert ana.campanas("/" + campana["id"]).status_code == 404


def test_una_campana_en_curso_no_se_elimina(ana: Sesion) -> None:
    campana = ana.crear_campana()
    poner_estado(campana, "running")
    assert ana.campanas("/" + campana["id"], "delete").status_code == 409
    assert Campaign.objects.exists()


def test_listar_pagina_y_filtra_por_estado(ana: Sesion, luis: Sesion) -> None:
    creadas = [ana.crear_campana(nombre=f"Campana {i}") for i in range(3)]
    luis.crear_campana()
    poner_estado(creadas[0], "completed")
    primera = ana.campanas(limite=2).json()
    assert [c["nombre"] for c in primera["datos"]] == ["Campana 2", "Campana 1"]
    segunda = ana.campanas(limite=2, cursor=primera["pagina"]["siguiente_cursor"]).json()
    assert [c["nombre"] for c in segunda["datos"]] == ["Campana 0"]
    completadas = ana.campanas(estado="completada").json()["datos"]
    assert [c["nombre"] for c in completadas] == ["Campana 0"]
    respuesta = ana.campanas(estado="pausada")
    assert (respuesta.status_code, respuesta.json()["campo"]) == (422, "estado")
    with CaptureQueriesContext(connection) as consultas:
        contenedor_campanas.listar_campanas().ejecutar(
            ana.public_id, FiltroCampanas(), PeticionPagina(2)
        )
    assert len(consultas) == 2


def test_subir_y_descargar_el_adjunto(ana: Sesion) -> None:
    campana = ana.crear_campana()
    respuesta = ana.subir(campana["id"], "video.mp4", MP4)
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["tiene_adjunto"] is True
    assert cuerpo["adjunto_url"] == f"/api/v1/campanas/{campana['id']}/adjunto"
    assert legacy(campana).media_url.startswith("memoria://")
    descarga = ana.campanas(f"/{campana['id']}/adjunto")
    assert descarga.status_code == 200
    assert descarga["Content-Type"] == "video/mp4"
    assert descarga["X-Content-Type-Options"] == "nosniff"
    assert descarga.content == MP4


def test_un_png_renombrado_como_mp4_responde_422(ana: Sesion) -> None:
    campana = ana.crear_campana()
    respuesta = ana.subir(campana["id"], "video.mp4", PNG)
    assert respuesta.status_code == 422
    assert respuesta.json()["campo"] == "archivo"
    assert legacy(campana).media_url is None


@pytest.mark.parametrize(
    ("nombre", "contenido"), [("doc.pdf", b"%PDF-1.7"), ("vacio.png", b""), ("foto.jpg", PNG)]
)
def test_otros_archivos_responden_422(ana: Sesion, nombre: str, contenido: bytes) -> None:
    campana = ana.crear_campana()
    assert ana.subir(campana["id"], nombre, contenido).status_code == 422


def test_sin_adjunto_la_descarga_responde_404(ana: Sesion) -> None:
    campana = ana.crear_campana()
    assert ana.campanas(f"/{campana['id']}/adjunto").status_code == 404


def test_si_el_almacen_no_responde_es_503_y_la_campana_queda_igual(
    ana: Sesion, settings: Any
) -> None:
    settings.ALMACEN_ARCHIVOS = "pocketbase"
    settings.POCKETBASE_URL = "http://127.0.0.1:9"
    settings.POCKETBASE_ADMIN_PASSWORD = "solo-pruebas"
    campana = ana.crear_campana()
    respuesta = ana.subir(campana["id"], "promo.png", PNG)
    assert respuesta.status_code == 503
    assert respuesta["Content-Type"] == "application/problem+json"
    assert legacy(campana).media_url is None


def test_una_campana_del_sistema_actual_aparece_en_la_v1(ana: Sesion) -> None:
    Campaign.objects.create(
        owner=ana.usuario, name="Vieja", message_template="Hola", target_tags="vip, lead"
    )
    (campana,) = ana.campanas().json()["datos"]
    assert id_publico(campana["id"])
    assert (campana["nombre"], campana["estado"], campana["etiquetas"]) == (
        "Vieja",
        "borrador",
        ["vip", "lead"],
    )
