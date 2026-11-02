from dataclasses import dataclass

from masssend.application.creditos.puertos import IConsultasCreditos, Movimiento, Paquete
from masssend.domain.creditos.repositorios import IRepoBilleteras
from masssend.domain.shared.identificadores import IdPublico
from masssend.domain.shared.paginacion import Pagina, PeticionPagina


@dataclass(frozen=True, slots=True)
class SaldoDTO:
    saldo: int
    reservado: int
    disponible: int


class ConsultarSaldo:
    def __init__(self, billeteras: IRepoBilleteras) -> None:
        self._billeteras = billeteras

    def ejecutar(self, dueno_id: IdPublico) -> SaldoDTO:
        billetera = self._billeteras.obtener(dueno_id)
        return SaldoDTO(billetera.saldo, billetera.reservado, billetera.disponible)


class ListarPaquetes:
    def __init__(self, consultas: IConsultasCreditos) -> None:
        self._consultas = consultas

    def ejecutar(self) -> list[Paquete]:
        return self._consultas.paquetes_activos()


class ListarMovimientos:
    def __init__(self, consultas: IConsultasCreditos) -> None:
        self._consultas = consultas

    def ejecutar(self, dueno_id: IdPublico, peticion: PeticionPagina) -> Pagina[Movimiento]:
        return self._consultas.movimientos(dueno_id, peticion)
