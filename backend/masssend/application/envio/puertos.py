"""Puertos que necesita el modulo de envio.

IReservaCreditos es la unica conexion entre las dos mitades del sistema.
Envio la define y creditos la implementa, sin conocerse entre si.
"""

from collections.abc import Sequence
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


@dataclass(frozen=True, slots=True)
class SolicitudEnvio:
    """envio_id viaja hasta el canal y vuelve en sus avisos: asi se correlaciona
    cada resultado con su mensaje, sin adivinar por el numero."""

    envio_id: IdPublico
    telefono: str
    texto: str
    adjunto: str | None = None


@dataclass(frozen=True, slots=True)
class ResultadoCanal:
    """Rechazado no es un error del sistema: el numero no existe o no tiene WhatsApp."""

    aceptado: bool
    id_externo: str | None = None
    motivo: str | None = None


class ICanalMensajeria(Protocol):
    """WhatsApp en la demostracion; un canal falso en las pruebas y en Postman."""

    def conectado(self) -> bool: ...

    def enviar(self, solicitud: SolicitudEnvio) -> ResultadoCanal:
        """Lanza ServicioNoDisponible si el canal no responde."""
        ...


@dataclass(frozen=True, slots=True)
class TrabajoEnvio:
    envio_id: IdPublico
    retraso_segundos: int


class IColaEnvios(Protocol):
    """Celery en la demostracion; sincrona en las pruebas y en Postman."""

    def publicar(self, trabajos: Sequence[TrabajoEnvio]) -> None:
        """Programa cada trabajo para que corra tras su retraso. Puede entregar
        un trabajo mas de una vez: procesarlo debe ser idempotente."""
        ...
