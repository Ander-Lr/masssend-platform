"""Trabajador de envios: python -m masssend.interfaces.workers.tareas_envio

Reemplaza al hilo _send_campaign_background. Toma de la base los envios
pendientes cuya hora ya llego y los procesa de a uno. Despues de cada mensaje
enviado espera el intervalo de PoliticaEnvio: con un solo numero de WhatsApp,
el ritmo se respeta aunque haya varias campanas o un atraso acumulado.
"""

import logging
import os
import threading

from masssend.application.envio.procesamiento import EnvioProcesado
from masssend.domain.envio.envio import EstadoEnvio
from masssend.domain.envio.politica import PoliticaEnvio

logger = logging.getLogger(__name__)
ESPERA_SIN_TRABAJO = 1.0


def procesar_siguiente() -> EnvioProcesado | None:
    """Procesa el proximo envio vencido. None si no habia ninguno."""
    from masssend.infrastructure.composition.envio import contenedor_envio

    envio_id = contenedor_envio.siguiente_vencido()
    if envio_id is None:
        return None
    return contenedor_envio.procesar_envio().ejecutar(envio_id)


def espera_tras(resultado: EnvioProcesado | None, politica: PoliticaEnvio) -> float:
    if resultado is None:
        return ESPERA_SIN_TRABAJO
    if resultado.estado is EstadoEnvio.ENVIADO and not resultado.repetido:
        return float(politica.segundos_entre_mensajes)
    return 0.0


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")
    import django

    django.setup()
    logger.info("Trabajador de envios iniciado.")
    politica = PoliticaEnvio()
    detenido = threading.Event()
    while not detenido.is_set():
        try:
            resultado = procesar_siguiente()
        except Exception:
            logger.exception("Fallo al procesar un envio; se reintenta en el siguiente ciclo.")
            resultado = None
        detenido.wait(espera_tras(resultado, politica))


if __name__ == "__main__":
    main()
