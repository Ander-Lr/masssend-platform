from dataclasses import dataclass

from masssend.domain.shared.errores import EstadoInvalido
from masssend.domain.shared.identificadores import IdPublico


@dataclass
class Reserva:
    id: IdPublico
    dueno_id: IdPublico
    campana_id: IdPublico
    cantidad: int
    restante: int

    def consumir(self) -> None:
        if self.restante == 0:
            raise EstadoInvalido("La reserva no tiene créditos pendientes.")
        self.restante -= 1

    def liberar(self) -> int:
        liberados, self.restante = self.restante, 0
        return liberados
