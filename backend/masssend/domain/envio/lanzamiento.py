"""Lanzamiento: une una campana con la reserva de creditos que la paga.

Se guarda al lanzar y se consulta al procesar cada envio (para cobrar), al
terminar y al cancelar (para devolver lo que no se uso).
"""

from dataclasses import dataclass

from masssend.domain.shared.errores import DatosInvalidos
from masssend.domain.shared.identificadores import IdPublico


@dataclass(frozen=True, slots=True)
class Lanzamiento:
    campana_id: IdPublico
    owner_id: IdPublico
    reserva_id: IdPublico
    total: int

    def __post_init__(self) -> None:
        if self.total < 1:
            raise DatosInvalidos("Un lanzamiento necesita al menos un destinatario.", "total")
