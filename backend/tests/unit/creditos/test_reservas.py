from dataclasses import dataclass, field

import pytest

from masssend.application.creditos.consultas import ConsultarSaldo
from masssend.application.creditos.reservas import (
    ConsumirCredito,
    LiberarReserva,
    ReservarCreditos,
)
from masssend.domain.creditos.repositorios import IRepoBilleteras, IRepoReservas
from masssend.domain.shared.errores import EstadoInvalido, RecursoNoEncontrado
from masssend.domain.shared.identificadores import IdPublico
from tests.fakes.creditos import RepoBilleterasMemoria, RepoReservasMemoria
from tests.fakes.ids import GeneradorIdsSecuencial
from tests.fakes.unidad_de_trabajo import UnidadDeTrabajoFalsa


@dataclass
class Entorno:
    ids: GeneradorIdsSecuencial = field(default_factory=GeneradorIdsSecuencial)
    uow: UnidadDeTrabajoFalsa = field(default_factory=UnidadDeTrabajoFalsa)
    reservas: RepoReservasMemoria = field(default_factory=RepoReservasMemoria)
    saldo: int = 10

    def __post_init__(self) -> None:
        self.billeteras = RepoBilleterasMemoria(self.reservas, self.saldo)
        self.ana = self.ids.nuevo()
        self.campana = self.ids.nuevo()

    def reservar(self, cantidad: int) -> IdPublico | None:
        caso = ReservarCreditos(self.billeteras, self.reservas, self.ids, self.uow)
        return caso.ejecutar(self.ana, self.campana, cantidad).reserva_id

    def consumir(self, reserva: IdPublico, mensaje: IdPublico) -> tuple[int, bool]:
        caso = ConsumirCredito(self.billeteras, self.reservas, self.uow)
        resultado = caso.ejecutar(reserva, mensaje)
        return resultado.restante, resultado.duplicado

    def liberar(self, reserva: IdPublico) -> int:
        return LiberarReserva(self.billeteras, self.reservas, self.uow).ejecutar(reserva)

    def saldos(self) -> tuple[int, int, int]:
        dto = ConsultarSaldo(self.billeteras).ejecutar(self.ana)
        return dto.saldo, dto.reservado, dto.disponible


def reserva_valida(e: Entorno, cantidad: int) -> IdPublico:
    reserva = e.reservar(cantidad)
    assert reserva is not None
    return reserva


def test_los_fakes_cumplen_los_repositorios() -> None:
    e = Entorno()
    billeteras: IRepoBilleteras = e.billeteras
    reservas: IRepoReservas = e.reservas
    assert billeteras and reservas


def test_reservar_no_descuenta_el_saldo() -> None:
    e = Entorno()
    reserva_valida(e, 4)
    assert e.saldos() == (10, 4, 6)


def test_sin_saldo_no_crea_la_reserva() -> None:
    e = Entorno(saldo=1)
    assert e.reservar(2) is None
    assert e.reservas.reservas == {}


def test_cada_mensaje_descuenta_un_credito() -> None:
    e = Entorno()
    reserva = reserva_valida(e, 2)
    assert e.consumir(reserva, e.ids.nuevo()) == (1, False)
    assert e.saldos() == (9, 1, 8)


def test_el_mismo_mensaje_se_cobra_una_vez() -> None:
    e = Entorno()
    reserva = reserva_valida(e, 2)
    mensaje = e.ids.nuevo()
    e.consumir(reserva, mensaje)
    assert e.consumir(reserva, mensaje) == (1, True)
    assert e.saldos() == (9, 1, 8)


def test_no_se_consume_por_encima_de_la_reserva() -> None:
    e = Entorno()
    reserva = reserva_valida(e, 1)
    e.consumir(reserva, e.ids.nuevo())
    with pytest.raises(EstadoInvalido):
        e.consumir(reserva, e.ids.nuevo())


def test_liberar_devuelve_solo_lo_pendiente_y_es_repetible() -> None:
    e = Entorno()
    reserva = reserva_valida(e, 3)
    e.consumir(reserva, e.ids.nuevo())
    assert e.liberar(reserva) == 2
    assert e.liberar(reserva) == 0
    assert e.saldos() == (9, 0, 9)


def test_tras_liberar_no_se_puede_consumir() -> None:
    e = Entorno()
    reserva = reserva_valida(e, 1)
    e.liberar(reserva)
    with pytest.raises(EstadoInvalido):
        e.consumir(reserva, e.ids.nuevo())


def test_una_reserva_inexistente_no_se_encuentra() -> None:
    e = Entorno()
    with pytest.raises(RecursoNoEncontrado):
        e.liberar(e.ids.nuevo())
    with pytest.raises(RecursoNoEncontrado):
        e.consumir(e.ids.nuevo(), e.ids.nuevo())
