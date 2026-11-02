"""Compra de un paquete. El precio y los creditos los fija siempre el servidor."""

from dataclasses import dataclass
from enum import StrEnum

from masssend.domain.shared.dinero import Dinero
from masssend.domain.shared.identificadores import IdPublico


class EstadoCompra(StrEnum):
    PENDIENTE = "pendiente"
    APROBADA = "aprobada"
    RECHAZADA = "rechazada"


@dataclass
class Compra:
    id: IdPublico
    dueno_id: IdPublico
    paquete_id: int
    pasarela: str
    referencia: str
    monto: Dinero
    creditos: int
    estado: EstadoCompra = EstadoCompra.PENDIENTE

    @property
    def aprobada(self) -> bool:
        return self.estado is EstadoCompra.APROBADA

    def aprobar(self) -> None:
        """Una compra rechazada puede aprobarse: la pasarela puede tardar."""
        self.estado = EstadoCompra.APROBADA

    def rechazar(self) -> None:
        if not self.aprobada:
            self.estado = EstadoCompra.RECHAZADA
