"""Reservar, consumir y liberar. Siempre: billetera primero, reserva despues."""

from dataclasses import dataclass

from masssend.application.shared.puertos import IGeneradorIds, IUnidadDeTrabajo
from masssend.domain.creditos.repositorios import IRepoBilleteras, IRepoReservas
from masssend.domain.creditos.reserva import Reserva
from masssend.domain.shared.identificadores import IdPublico


@dataclass(frozen=True, slots=True)
class ResultadoReservar:
    reserva_id: IdPublico | None
    cantidad: int
    disponible: int


@dataclass(frozen=True, slots=True)
class ResultadoConsumir:
    reserva_id: IdPublico
    restante: int
    duplicado: bool


class ReservarCreditos:
    def __init__(
        self,
        billeteras: IRepoBilleteras,
        reservas: IRepoReservas,
        ids: IGeneradorIds,
        uow: IUnidadDeTrabajo,
    ) -> None:
        self._billeteras = billeteras
        self._reservas = reservas
        self._ids = ids
        self._uow = uow

    def ejecutar(
        self, dueno_id: IdPublico, campana_id: IdPublico, cantidad: int
    ) -> ResultadoReservar:
        with self._uow:
            billetera = self._billeteras.bloquear(dueno_id)
            disponible = billetera.disponible
            if not billetera.reservar(cantidad):
                return ResultadoReservar(None, cantidad, disponible)
            reserva = Reserva(self._ids.nuevo(), dueno_id, campana_id, cantidad, cantidad)
            self._reservas.agregar(reserva)
            self._billeteras.guardar(billetera)
            return ResultadoReservar(reserva.id, cantidad, billetera.disponible)


class ConsumirCredito:
    def __init__(
        self,
        billeteras: IRepoBilleteras,
        reservas: IRepoReservas,
        uow: IUnidadDeTrabajo,
    ) -> None:
        self._billeteras = billeteras
        self._reservas = reservas
        self._uow = uow

    def ejecutar(self, reserva_id: IdPublico, mensaje_id: IdPublico) -> ResultadoConsumir:
        dueno_id = self._reservas.obtener(reserva_id).dueno_id
        with self._uow:
            billetera = self._billeteras.bloquear(dueno_id)
            reserva = self._reservas.bloquear(reserva_id)
            if self._reservas.ya_consumido(reserva_id, mensaje_id):
                return ResultadoConsumir(reserva_id, reserva.restante, True)
            reserva.consumir()
            billetera.consumir()
            self._reservas.guardar(reserva)
            self._reservas.registrar_consumo(reserva, mensaje_id)
            self._billeteras.guardar(billetera)
            return ResultadoConsumir(reserva_id, reserva.restante, False)


class LiberarReserva:
    def __init__(
        self,
        billeteras: IRepoBilleteras,
        reservas: IRepoReservas,
        uow: IUnidadDeTrabajo,
    ) -> None:
        self._billeteras = billeteras
        self._reservas = reservas
        self._uow = uow

    def ejecutar(self, reserva_id: IdPublico) -> int:
        dueno_id = self._reservas.obtener(reserva_id).dueno_id
        with self._uow:
            billetera = self._billeteras.bloquear(dueno_id)
            reserva = self._reservas.bloquear(reserva_id)
            liberados = reserva.liberar()
            if liberados:
                billetera.liberar(liberados)
                self._reservas.guardar(reserva)
            return liberados
