"""Trabajador de la cola de correos: python -m masssend.interfaces.workers.tareas_correo"""

import logging
import os
import threading


def procesar_pendientes(maximo: int = 100) -> int:
    """Procesa hasta `maximo` tareas y devuelve cuantas atendio."""
    from masssend.infrastructure.composition.identidad import contenedor_identidad

    procesador = contenedor_identidad.procesador_cola()
    atendidas = 0
    while atendidas < maximo and procesador.procesar_siguiente():
        atendidas += 1
    return atendidas


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")
    import django

    django.setup()
    from django.conf import settings

    logging.getLogger(__name__).info("Trabajador de correos iniciado.")
    espera = settings.EMAIL_QUEUE_INTERVAL_MS / 1000
    detenido = threading.Event()
    while not detenido.is_set():
        procesar_pendientes()
        detenido.wait(espera)


if __name__ == "__main__":
    main()
