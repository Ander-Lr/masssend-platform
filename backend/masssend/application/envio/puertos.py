"""Puertos que necesita el modulo de envio.

IReservaCreditos es la unica conexion entre las dos mitades del sistema.
Envio la define y creditos la implementa, sin conocerse entre si.
"""

from dataclasses import dataclass
from typing import Protocol

from masssend.domain.shared.identificadores import IdPublico


@dataclass(frozen=True, slots=True)
class ReservaCreada:
    reserva_id: IdPublico
    cantidad: int


@dataclass(frozen=True, slots=True)
class ReservaRechazada:
    """Resultado esperado cuando no alcanza el saldo; la API responde 402."""

    requerido: int
    disponible: int


ResultadoReserva = ReservaCreada | ReservaRechazada


@dataclass(frozen=True, slots=True)
class ConsumoRealizado:
    """Si duplicado es True, ese mensaje ya se habia cobrado antes."""

    reserva_id: IdPublico
    restante: int
    duplicado: bool = False


@dataclass(frozen=True, slots=True)
class LiberacionRealizada:
    reserva_id: IdPublico
    liberados: int


class IReservaCreditos(Protocol):
    def reservar(
        self, owner_id: IdPublico, campana_id: IdPublico, cantidad: int
    ) -> ResultadoReserva:
        """Aparta creditos al lanzar. No descuenta el saldo todavia."""
        ...

    def consumir(self, reserva_id: IdPublico, mensaje_id: IdPublico) -> ConsumoRealizado:
        """Cobra un credito cuando el mensaje sale.

        Es idempotente por mensaje: repetirlo no cobra dos veces. Lanza
        RecursoNoEncontrado si no existe y EstadoInvalido si no queda reserva.
        """
        ...

    def liberar(self, reserva_id: IdPublico) -> LiberacionRealizada:
        """Devuelve lo no consumido. Repetirlo libera cero."""
        ...
