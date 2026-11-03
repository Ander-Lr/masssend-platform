"""Cola sobre la propia tabla de envios.

Publicar solo fija programado_para segun el ritmo de PoliticaEnvio. El
trabajador tareas_envio toma los vencidos. No hace falta otro servicio y, si
algo se reinicia, los pendientes siguen en la base y se retoman.
"""

from collections.abc import Sequence

from masssend.application.envio.puertos import TrabajoEnvio
from masssend.application.shared.puertos import IReloj
from masssend.infrastructure.persistence.envio.repositorios import RepoEnviosDjango


class ColaBaseDatos:
    def __init__(self, reloj: IReloj) -> None:
        self._reloj = reloj

    def publicar(self, trabajos: Sequence[TrabajoEnvio]) -> None:
        RepoEnviosDjango.programar_desde(
            self._reloj.ahora(), {t.envio_id: t.retraso_segundos for t in trabajos}
        )
