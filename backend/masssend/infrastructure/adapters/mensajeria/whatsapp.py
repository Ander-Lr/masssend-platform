"""Canal de WhatsApp sobre el gateway Node.js de backend/whatsapp_api.

Hace lo mismo que _send_campaign_background: el adjunto viaja en base64,
porque el gateway nunca conoce la URL privada del almacen. Ademas envia el
envio_id, para que el gateway lo devuelva con el resultado.
"""

import base64
import logging
from typing import Any

import requests
from django.conf import settings

from masssend.application.campanas.puertos import ArchivoDescargado, IAlmacenArchivos
from masssend.application.envio.puertos import EstadoConexion, ResultadoCanal, SolicitudEnvio
from masssend.domain.shared.errores import EstadoInvalido, ServicioNoDisponible

logger = logging.getLogger(__name__)

NO_DISPONIBLE = "WhatsApp no está disponible."
_adjuntos: dict[str, ArchivoDescargado] = {}
MAX_ADJUNTOS_EN_CACHE = 4


class CanalWhatsApp:
    def __init__(self, almacen: IAlmacenArchivos, timeout: int = 30) -> None:
        self._almacen = almacen
        self._timeout = timeout

    @property
    def _url(self) -> str:
        return str(settings.WHATSAPP_API_URL).rstrip("/")

    def conectado(self) -> bool:
        try:
            respuesta = requests.get(f"{self._url}/api/status", timeout=5)
            return bool(respuesta.ok and respuesta.json().get("ready"))
        except (requests.RequestException, ValueError):
            logger.warning("No se pudo consultar el estado de WhatsApp.")
            return False

    def enviar(self, solicitud: SolicitudEnvio) -> ResultadoCanal:
        cuerpo: dict[str, Any] = {
            "number": solicitud.telefono,
            "message": solicitud.texto,
            "envio_id": str(solicitud.envio_id),
        }
        if solicitud.adjunto:
            cuerpo.update(self._adjunto(solicitud.adjunto))
        try:
            respuesta = requests.post(f"{self._url}/api/send", json=cuerpo, timeout=self._timeout)
        except requests.RequestException as error:
            raise ServicioNoDisponible(NO_DISPONIBLE) from error
        if respuesta.status_code in (400, 422):
            return ResultadoCanal(False, motivo=_error(respuesta))
        if not respuesta.ok:
            raise ServicioNoDisponible(_error(respuesta))
        datos = _json(respuesta)
        return ResultadoCanal(True, id_externo=datos.get("wpp_message_id"))

    def _adjunto(self, referencia: str) -> dict[str, str]:
        """Se descarga una vez y se reutiliza para todos los mensajes de la campana."""
        archivo = _adjuntos.get(referencia) or self._almacen.obtener(referencia)
        if archivo is None:
            return {}
        if referencia not in _adjuntos:
            if len(_adjuntos) >= MAX_ADJUNTOS_EN_CACHE:
                _adjuntos.pop(next(iter(_adjuntos)))
            _adjuntos[referencia] = archivo
        return {
            "media_base64": base64.b64encode(archivo.contenido).decode(),
            "media_mimetype": archivo.tipo,
            "media_filename": archivo.nombre,
        }


class ConexionWhatsApp:
    """Lo que hacian api_qr_status, api_request_pairing y api_cambiar_numero."""

    @property
    def _url(self) -> str:
        return str(settings.WHATSAPP_API_URL).rstrip("/")

    def _pedir(self, metodo: str, ruta: str, **datos: Any) -> requests.Response:
        try:
            return requests.request(metodo, f"{self._url}{ruta}", timeout=15, **datos)
        except requests.RequestException as error:
            raise ServicioNoDisponible(NO_DISPONIBLE) from error

    def estado(self) -> EstadoConexion:
        datos = _json(self._pedir("GET", "/api/qr"))
        conectado = bool(datos.get("ready"))
        codigo = datos.get("pairing_code") or None
        # Con un codigo pedido, el QR ya no sirve: se muestra uno u otro.
        qr = None if conectado or codigo else (datos.get("qr") or None)
        return EstadoConexion(conectado, codigo, qr)

    def solicitar_vinculacion(self, telefono: str) -> str | None:
        respuesta = self._pedir("POST", "/api/request-pairing", json={"phone": telefono})
        datos = _json(respuesta)
        if respuesta.status_code == 400:
            raise EstadoInvalido(str(datos.get("error") or "No se pudo vincular el número."))
        if not respuesta.ok:
            raise ServicioNoDisponible(_error(respuesta))
        return datos.get("code") or None

    def cerrar_sesion(self) -> None:
        respuesta = self._pedir("POST", "/api/logout")
        if not respuesta.ok:
            raise ServicioNoDisponible(_error(respuesta))


def _json(respuesta: requests.Response) -> dict[str, Any]:
    try:
        datos = respuesta.json()
    except ValueError:
        return {}
    return datos if isinstance(datos, dict) else {}


def _error(respuesta: requests.Response) -> str:
    return str(_json(respuesta).get("error") or f"WhatsApp respondió {respuesta.status_code}.")
