"""Canal falso para el perfil ci y las pruebas: no sale nada a WhatsApp.

Para poder probar rechazos desde Postman, un numero que termina en 0000 se
trata como un numero sin WhatsApp.
"""

import logging

from masssend.application.envio.puertos import EstadoConexion, ResultadoCanal, SolicitudEnvio
from masssend.domain.shared.errores import EstadoInvalido

logger = logging.getLogger(__name__)

SUFIJO_RECHAZADO = "0000"


class CanalFalso:
    def conectado(self) -> bool:
        return True

    def enviar(self, solicitud: SolicitudEnvio) -> ResultadoCanal:
        if solicitud.telefono.endswith(SUFIJO_RECHAZADO):
            return ResultadoCanal(False, motivo="El número no tiene WhatsApp.")
        logger.info("Canal falso: mensaje %s a %s", solicitud.envio_id, solicitud.telefono)
        return ResultadoCanal(True, id_externo=f"falso-{solicitud.envio_id}")


class ConexionFalsa:
    """En el perfil ci el canal falso siempre esta conectado."""

    def estado(self) -> EstadoConexion:
        return EstadoConexion(conectado=True)

    def solicitar_vinculacion(self, telefono: str) -> str | None:
        raise EstadoInvalido("Ya hay un número conectado.")

    def cerrar_sesion(self) -> None:
        logger.info("Canal falso: cierre de sesión ignorado.")
