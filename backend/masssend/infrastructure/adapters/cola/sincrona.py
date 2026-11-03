"""Cola sincrona para el perfil ci: procesa cada trabajo al instante, sin esperas.

Asi una coleccion de Postman ve la campana completada en la misma respuesta
del lanzamiento. Un trabajo que falla no detiene a los demas.
"""

import logging
from collections.abc import Callable, Sequence

from masssend.application.envio.puertos import TrabajoEnvio
from masssend.domain.shared.identificadores import IdPublico

logger = logging.getLogger(__name__)


class ColaSincrona:
    def __init__(self, procesar: Callable[[IdPublico], object]) -> None:
        self._procesar = procesar

    def publicar(self, trabajos: Sequence[TrabajoEnvio]) -> None:
        for trabajo in trabajos:
            try:
                self._procesar(trabajo.envio_id)
            except Exception:
                logger.exception("Fallo el envio %s.", trabajo.envio_id)
