"""Reutiliza el envio y los reintentos actuales de la cola de correos."""

import logging

from email_auth.management.commands.process_email_queue import process_next_task

logger = logging.getLogger(__name__)


class _Registro:
    def write(self, mensaje: str) -> None:
        logger.info("%s", mensaje)


class ProcesadorCola:
    def procesar_siguiente(self) -> bool:
        return bool(process_next_task(_Registro()))
