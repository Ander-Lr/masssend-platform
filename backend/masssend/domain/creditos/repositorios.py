from typing import Protocol

from masssend.domain.creditos.billetera import Billetera
from masssend.domain.creditos.compra import Compra
from masssend.domain.creditos.reserva import Reserva
from masssend.domain.shared.identificadores import IdPublico


class IRepoBilleteras(Protocol):
    def obtener(self, dueno_id: IdPublico) -> Billetera: ...

    def bloquear(self, dueno_id: IdPublico) -> Billetera:
        """Retiene la fila hasta confirmar. Toda operacion bloquea primero la billetera."""
        ...

    def guardar(self, billetera: Billetera) -> None: ...


class IRepoReservas(Protocol):
    def agregar(self, reserva: Reserva) -> None: ...

    def obtener(self, reserva_id: IdPublico) -> Reserva:
        """Lanza RecursoNoEncontrado si no existe."""
        ...

    def bloquear(self, reserva_id: IdPublico) -> Reserva: ...

    def guardar(self, reserva: Reserva) -> None: ...

    def ya_consumido(self, reserva_id: IdPublico, mensaje_id: IdPublico) -> bool: ...

    def registrar_consumo(self, reserva: Reserva, mensaje_id: IdPublico) -> None: ...


class IRepoCompras(Protocol):
    def agregar(self, compra: Compra) -> None: ...

    def obtener(self, compra_id: IdPublico) -> Compra:
        """Lanza RecursoNoEncontrado si no existe."""
        ...

    def bloquear(self, compra_id: IdPublico) -> Compra: ...

    def guardar(self, compra: Compra, respuesta: dict[str, object]) -> None: ...
