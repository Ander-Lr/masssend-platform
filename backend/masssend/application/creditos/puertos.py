from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from masssend.domain.shared.dinero import Dinero
from masssend.domain.shared.identificadores import IdPublico
from masssend.domain.shared.paginacion import Pagina, PeticionPagina


@dataclass(frozen=True, slots=True)
class Paquete:
    id: int
    nombre: str
    creditos: int
    precio: Dinero


@dataclass(frozen=True, slots=True)
class Movimiento:
    tipo: str
    creditos: int
    fecha: datetime
    detalle: str


class IConsultasCreditos(Protocol):
    def paquetes_activos(self) -> list[Paquete]: ...

    def movimientos(
        self, dueno_id: IdPublico, peticion: PeticionPagina
    ) -> Pagina[Movimiento]: ...
