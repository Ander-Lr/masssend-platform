"""Puertos que necesita el modulo de envio.

IReservaCreditos es la unica conexion entre las dos mitades del sistema.
Envio la define y creditos la implementa, sin conocerse entre si.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from masssend.domain.envio.entrega import EstadoEntrega
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


class IHistorialMensajes(Protocol):
    """El historial de mensajes del sistema actual, que leen el chat y los reportes."""

    def registrar_entrante(self, telefono: str, texto: str, id_externo: str | None) -> bool:
        """Guarda un mensaje recibido. False si ese id ya se habia registrado."""
        ...

    def registrar_acuse(self, id_externo: str, estado: EstadoEntrega) -> int:
        """Avanza el estado de entrega; nunca retrocede. Devuelve cuantos cambiaron."""
        ...

    def registrar_resultado_sin_envio(
        self, telefono: str, enviado: bool, id_externo: str | None, motivo: str | None
    ) -> int:
        """Resultado de un mensaje que no salio de una campana v1 (el chat del panel)."""
        ...

    def registrar_saliente(self, owner_id: IdPublico, telefono: str, texto: str) -> IdPublico:
        """Guarda un mensaje del chat como pendiente y devuelve su id publico."""
        ...

    def registrar_resultado_de_mensaje(
        self, mensaje_id: IdPublico, enviado: bool, id_externo: str | None, motivo: str | None
    ) -> int:
        """Resultado de un mensaje del chat v1, que viaja con su propio id. Solo cambia
        un pendiente: repetirlo no cambia nada. 0 si no existe."""
        ...


@dataclass(frozen=True, slots=True)
class EstadoConexion:
    conectado: bool
    codigo_vinculacion: str | None = None
    # Texto del QR que muestra WhatsApp mientras espera; el navegador lo dibuja.
    qr: str | None = None


class IConexionWhatsApp(Protocol):
    """Vinculacion del numero de la plataforma.

    Lanza ServicioNoDisponible si el gateway no responde.
    """

    def estado(self) -> EstadoConexion: ...

    def solicitar_vinculacion(self, telefono: str) -> str | None:
        """Devuelve el codigo que se escribe en WhatsApp, o None si el gateway aun lo
        esta generando (aparece luego en estado). Lanza EstadoInvalido si ya hay un
        numero conectado."""
        ...

    def cerrar_sesion(self) -> None: ...
