from dataclasses import dataclass, field

from masssend.application.envio.puertos import (
    ConsumoRealizado,
    LiberacionRealizada,
    ReservaCreada,
    ReservaRechazada,
    ResultadoReserva,
)
from masssend.domain.shared.errores import DatosInvalidos, EstadoInvalido, RecursoNoEncontrado
from masssend.domain.shared.identificadores import IdPublico
from tests.fakes.ids import GeneradorIdsSecuencial


@dataclass
class _Reserva:
    owner_id: IdPublico
    restante: int
    consumidos: set[IdPublico] = field(default_factory=set)


class ReservaCreditosFalsa:
    """Implementacion en memoria de IReservaCreditos para el modulo de envio."""

    def __init__(self, saldo: int = 0) -> None:
        self._saldos: dict[IdPublico, int] = {}
        self._saldo_inicial = saldo
        self._reservas: dict[IdPublico, _Reserva] = {}
        self._ids = GeneradorIdsSecuencial()

    def saldo(self, owner_id: IdPublico) -> int:
        """Saldo real: baja con cada consumo, no al reservar."""
        return self._saldos.get(owner_id, self._saldo_inicial)

    def reservado(self, owner_id: IdPublico) -> int:
        return sum(r.restante for r in self._reservas.values() if r.owner_id == owner_id)

    def reservar(
        self, owner_id: IdPublico, campana_id: IdPublico, cantidad: int
    ) -> ResultadoReserva:
        if cantidad <= 0:
            raise DatosInvalidos("La cantidad debe ser mayor que cero.", "cantidad")
        disponible = self.saldo(owner_id) - self.reservado(owner_id)
        if cantidad > disponible:
            return ReservaRechazada(requerido=cantidad, disponible=disponible)
        reserva_id = self._ids.nuevo()
        self._reservas[reserva_id] = _Reserva(owner_id, cantidad)
        return ReservaCreada(reserva_id, cantidad)

    def consumir(self, reserva_id: IdPublico, mensaje_id: IdPublico) -> ConsumoRealizado:
        reserva = self._obtener(reserva_id)
        if mensaje_id in reserva.consumidos:
            return ConsumoRealizado(reserva_id, reserva.restante, duplicado=True)
        if reserva.restante == 0:
            raise EstadoInvalido("La reserva no tiene creditos pendientes.")
        reserva.consumidos.add(mensaje_id)
        reserva.restante -= 1
        self._saldos[reserva.owner_id] = self.saldo(reserva.owner_id) - 1
        return ConsumoRealizado(reserva_id, reserva.restante)

    def liberar(self, reserva_id: IdPublico) -> LiberacionRealizada:
        reserva = self._obtener(reserva_id)
        liberados, reserva.restante = reserva.restante, 0
        return LiberacionRealizada(reserva_id, liberados)

    def _obtener(self, reserva_id: IdPublico) -> _Reserva:
        try:
            return self._reservas[reserva_id]
        except KeyError as error:
            raise RecursoNoEncontrado("La reserva no existe.") from error
