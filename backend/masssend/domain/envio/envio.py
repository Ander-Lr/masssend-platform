"""Envio: un mensaje de una campana a un contacto, y el progreso de todos ellos.

    pendiente ──> enviado
        │──────> fallido     el canal lo rechazo; no se cobra
        │──────> omitido     el contacto se dio de baja o ya no existe; no se cobra
        └──────> cancelado   la campana se cancelo antes de que saliera

Solo un envio pendiente se procesa. Asi, si la cola entrega el mismo trabajo
dos veces, la segunda no hace nada: el mensaje sale y se cobra una sola vez.
"""

from dataclasses import dataclass
from enum import StrEnum

from masssend.domain.shared.errores import EstadoInvalido
from masssend.domain.shared.identificadores import IdPublico

MAX_DETALLE = 500


class EstadoEnvio(StrEnum):
    PENDIENTE = "pendiente"
    ENVIADO = "enviado"
    FALLIDO = "fallido"
    OMITIDO = "omitido"
    CANCELADO = "cancelado"


@dataclass
class Envio:
    id: IdPublico
    campana_id: IdPublico
    owner_id: IdPublico
    contacto_id: IdPublico
    telefono: str
    orden: int
    estado: EstadoEnvio = EstadoEnvio.PENDIENTE
    id_externo: str | None = None
    detalle: str | None = None

    @property
    def pendiente(self) -> bool:
        return self.estado is EstadoEnvio.PENDIENTE

    def _cerrar(self, estado: EstadoEnvio, detalle: str | None = None) -> None:
        if not self.pendiente:
            raise EstadoInvalido(f"El envío ya está {self.estado}.")
        self.estado = estado
        self.detalle = detalle[:MAX_DETALLE] if detalle else None

    def marcar_enviado(self, id_externo: str | None) -> None:
        self._cerrar(EstadoEnvio.ENVIADO)
        self.id_externo = id_externo

    def marcar_fallido(self, motivo: str) -> None:
        self._cerrar(EstadoEnvio.FALLIDO, motivo)

    def omitir(self, motivo: str) -> None:
        self._cerrar(EstadoEnvio.OMITIDO, motivo)

    def cancelar(self) -> None:
        self._cerrar(EstadoEnvio.CANCELADO)


@dataclass(frozen=True, slots=True)
class Progreso:
    total: int = 0
    enviados: int = 0
    fallidos: int = 0
    omitidos: int = 0
    cancelados: int = 0

    @property
    def pendientes(self) -> int:
        return self.total - self.procesados

    @property
    def procesados(self) -> int:
        return self.enviados + self.fallidos + self.omitidos + self.cancelados

    @property
    def porcentaje(self) -> int:
        """Avance entero de 0 a 100. Sin envios, una campana no tiene avance."""
        return self.procesados * 100 // self.total if self.total else 0

    @property
    def terminado(self) -> bool:
        return self.total > 0 and self.pendientes == 0
