from collections.abc import Sequence
from typing import Protocol

from masssend.domain.envio.envio import Envio, Progreso
from masssend.domain.envio.lanzamiento import Lanzamiento
from masssend.domain.shared.identificadores import IdPublico


class IRepoEnvios(Protocol):
    def agregar_varios(self, envios: Sequence[Envio]) -> None:
        """Inserta en bloque: se usa al lanzar, de a una pagina de destinatarios."""
        ...

    def bloquear(self, envio_id: IdPublico) -> Envio | None:
        """Retiene la fila hasta confirmar, para que dos trabajadores no lo procesen
        a la vez. None si no existe."""
        ...

    def guardar(self, envio: Envio) -> None: ...

    def cancelar_pendientes(self, campana_id: IdPublico) -> int:
        """Marca como cancelados los pendientes y devuelve cuantos eran."""
        ...

    def progreso(self, campana_id: IdPublico) -> Progreso:
        """Cuenta por estado en una sola consulta."""
        ...


class IRepoLanzamientos(Protocol):
    def agregar(self, lanzamiento: Lanzamiento) -> None: ...

    def obtener(self, campana_id: IdPublico) -> Lanzamiento | None: ...
