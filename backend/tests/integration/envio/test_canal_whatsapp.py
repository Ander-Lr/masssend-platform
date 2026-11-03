"""El adaptador de WhatsApp contra un gateway simulado: sin red ni numero real."""

from typing import Any

import pytest
import requests

from masssend.application.campanas.puertos import ArchivoDescargado
from masssend.application.envio.puertos import SolicitudEnvio
from masssend.domain.shared.errores import ServicioNoDisponible
from masssend.infrastructure.adapters.mensajeria import whatsapp
from masssend.infrastructure.adapters.mensajeria.whatsapp import CanalWhatsApp
from masssend.infrastructure.composition.root import contenedor


class Respuesta:
    def __init__(self, estado: int, cuerpo: Any) -> None:
        self.status_code = estado
        self.ok = 200 <= estado < 300
        self._cuerpo = cuerpo

    def json(self) -> Any:
        if isinstance(self._cuerpo, Exception):
            raise self._cuerpo
        return self._cuerpo


class Almacen:
    def __init__(self) -> None:
        self.descargas = 0

    def guardar(self, *_: Any) -> str:
        return "ref"

    def obtener(self, referencia: str) -> ArchivoDescargado | None:
        self.descargas += 1
        return ArchivoDescargado("promo.png", "image/png", b"PNG")


@pytest.fixture
def peticiones(monkeypatch: pytest.MonkeyPatch, settings: Any) -> list[tuple[str, Any]]:
    settings.WHATSAPP_API_URL = "http://gateway:3001/"
    hechas: list[tuple[str, Any]] = []
    respuestas: dict[str, Any] = {}

    def falsa(metodo: str) -> Any:
        def llamar(url: str, json: Any = None, timeout: int = 0) -> Any:
            hechas.append((f"{metodo} {url}", json))
            respuesta = respuestas[metodo]
            if isinstance(respuesta, Exception):
                raise respuesta
            return respuesta

        return llamar

    monkeypatch.setattr(whatsapp.requests, "get", falsa("GET"))
    monkeypatch.setattr(whatsapp.requests, "post", falsa("POST"))
    whatsapp._adjuntos.clear()
    hechas.append(("respuestas", respuestas))
    return hechas


def responder(peticiones: list[tuple[str, Any]], metodo: str, respuesta: Any) -> None:
    peticiones[0][1][metodo] = respuesta


def solicitud(adjunto: str | None = None) -> SolicitudEnvio:
    return SolicitudEnvio(contenedor.generador_ids().nuevo(), "593991112222", "Hola", adjunto)


def test_conectado_lee_el_estado_del_gateway(peticiones: list[tuple[str, Any]]) -> None:
    canal = CanalWhatsApp(Almacen())
    responder(peticiones, "GET", Respuesta(200, {"ready": True}))
    assert canal.conectado()
    assert peticiones[-1][0] == "GET http://gateway:3001/api/status"
    responder(peticiones, "GET", Respuesta(200, {"ready": False}))
    assert not canal.conectado()
    responder(peticiones, "GET", requests.ConnectionError())
    assert not canal.conectado()


def test_enviar_incluye_el_envio_id(peticiones: list[tuple[str, Any]]) -> None:
    responder(peticiones, "POST", Respuesta(200, {"success": True, "status": "queued"}))
    pedido = solicitud()
    resultado = CanalWhatsApp(Almacen()).enviar(pedido)
    assert resultado.aceptado
    url, cuerpo = peticiones[-1]
    assert url == "POST http://gateway:3001/api/send"
    assert cuerpo == {"number": "593991112222", "message": "Hola", "envio_id": str(pedido.envio_id)}


def test_el_adjunto_viaja_en_base64_y_se_descarga_una_vez(
    peticiones: list[tuple[str, Any]],
) -> None:
    responder(peticiones, "POST", Respuesta(200, {"success": True}))
    almacen = Almacen()
    canal = CanalWhatsApp(almacen)
    canal.enviar(solicitud("ref-1"))
    canal.enviar(solicitud("ref-1"))
    cuerpo = peticiones[-1][1]
    assert (cuerpo["media_base64"], cuerpo["media_mimetype"]) == ("UE5H", "image/png")
    assert almacen.descargas == 1


@pytest.mark.parametrize("estado", [400, 422])
def test_un_numero_rechazado_no_es_un_error(peticiones: list[tuple[str, Any]], estado: int) -> None:
    responder(peticiones, "POST", Respuesta(estado, {"error": "Numero invalido"}))
    resultado = CanalWhatsApp(Almacen()).enviar(solicitud())
    assert (resultado.aceptado, resultado.motivo) == (False, "Numero invalido")


@pytest.mark.parametrize(
    "respuesta", [Respuesta(503, {"error": "WhatsApp no conectado"}), Respuesta(500, ValueError())]
)
def test_un_gateway_caido_es_servicio_no_disponible(
    peticiones: list[tuple[str, Any]], respuesta: Respuesta
) -> None:
    responder(peticiones, "POST", respuesta)
    with pytest.raises(ServicioNoDisponible):
        CanalWhatsApp(Almacen()).enviar(solicitud())


def test_sin_red_es_servicio_no_disponible(peticiones: list[tuple[str, Any]]) -> None:
    responder(peticiones, "POST", requests.ConnectionError())
    with pytest.raises(ServicioNoDisponible):
        CanalWhatsApp(Almacen()).enviar(solicitud())
