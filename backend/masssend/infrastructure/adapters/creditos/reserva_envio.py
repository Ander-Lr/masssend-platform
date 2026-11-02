"""Implementacion real de IReservaCreditos: une envio y creditos sin que se conozcan."""

from masssend.application.creditos.reservas import (
    ConsumirCredito,
    LiberarReserva,
    ReservarCreditos,
)
from masssend.application.envio.puertos import (
    ConsumoRealizado,
    LiberacionRealizada,
    ReservaCreada,
    ReservaRechazada,
    ResultadoReserva,
)
from masssend.domain.shared.identificadores import IdPublico


class ReservaCreditosLocal:
    def __init__(
        self,
        reservar: ReservarCreditos,
        consumir: ConsumirCredito,
        liberar: LiberarReserva,
    ) -> None:
        self._reservar = reservar
        self._consumir = consumir
        self._liberar = liberar

    def reservar(
        self, owner_id: IdPublico, campana_id: IdPublico, cantidad: int
    ) -> ResultadoReserva:
        resultado = self._reservar.ejecutar(owner_id, campana_id, cantidad)
        if resultado.reserva_id is None:
            return ReservaRechazada(requerido=cantidad, disponible=resultado.disponible)
        return ReservaCreada(resultado.reserva_id, cantidad)

    def consumir(self, reserva_id: IdPublico, mensaje_id: IdPublico) -> ConsumoRealizado:
        resultado = self._consumir.ejecutar(reserva_id, mensaje_id)
        return ConsumoRealizado(reserva_id, resultado.restante, resultado.duplicado)

    def liberar(self, reserva_id: IdPublico) -> LiberacionRealizada:
        return LiberacionRealizada(reserva_id, self._liberar.ejecutar(reserva_id))
