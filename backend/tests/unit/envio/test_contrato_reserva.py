"""Contrato de IReservaCreditos: el adaptador real debera cumplir lo mismo."""

import pytest

from masssend.application.envio.puertos import (
    IReservaCreditos,
    ReservaCreada,
    ReservaRechazada,
)
from masssend.application.shared.puertos import IUnidadDeTrabajo
from masssend.domain.shared.errores import (
    DatosInvalidos,
    EstadoInvalido,
    RecursoNoEncontrado,
    SaldoInsuficiente,
)
from masssend.domain.shared.identificadores import IdPublico
from tests.fakes.ids import GeneradorIdsSecuencial
from tests.fakes.reserva_creditos import ReservaCreditosFalsa
from tests.fakes.unidad_de_trabajo import UnidadDeTrabajoFalsa

IDS = GeneradorIdsSecuencial()
ANA = IDS.nuevo()
CAMPANA = IDS.nuevo()
MENSAJE_1 = IDS.nuevo()
MENSAJE_2 = IDS.nuevo()


def reservar(creditos: ReservaCreditosFalsa, cantidad: int) -> ReservaCreada:
    resultado = creditos.reservar(ANA, CAMPANA, cantidad)
    assert isinstance(resultado, ReservaCreada)
    return resultado


def test_reservar_aparta_sin_descontar() -> None:
    creditos = ReservaCreditosFalsa(saldo=10)
    reservar(creditos, 4)
    assert creditos.saldo(ANA) == 10
    assert creditos.reservado(ANA) == 4


def test_sin_saldo_devuelve_rechazo_y_no_excepcion() -> None:
    creditos = ReservaCreditosFalsa(saldo=2)
    assert creditos.reservar(ANA, CAMPANA, 3) == ReservaRechazada(requerido=3, disponible=2)


def test_lo_reservado_no_se_puede_volver_a_reservar() -> None:
    creditos = ReservaCreditosFalsa(saldo=5)
    reservar(creditos, 4)
    assert creditos.reservar(ANA, CAMPANA, 2) == ReservaRechazada(requerido=2, disponible=1)


@pytest.mark.parametrize("cantidad", [0, -1])
def test_rechaza_cantidades_no_positivas(cantidad: int) -> None:
    with pytest.raises(DatosInvalidos):
        ReservaCreditosFalsa(saldo=5).reservar(ANA, CAMPANA, cantidad)


def test_consumir_descuenta_un_credito() -> None:
    creditos = ReservaCreditosFalsa(saldo=5)
    reserva = reservar(creditos, 2)
    assert creditos.consumir(reserva.reserva_id, MENSAJE_1).restante == 1
    assert creditos.saldo(ANA) == 4


def test_el_mismo_mensaje_no_se_cobra_dos_veces() -> None:
    creditos = ReservaCreditosFalsa(saldo=5)
    reserva = reservar(creditos, 2)
    creditos.consumir(reserva.reserva_id, MENSAJE_1)
    repetido = creditos.consumir(reserva.reserva_id, MENSAJE_1)
    assert repetido.duplicado
    assert creditos.saldo(ANA) == 4


def test_no_consume_mas_de_lo_reservado() -> None:
    creditos = ReservaCreditosFalsa(saldo=5)
    reserva = reservar(creditos, 1)
    creditos.consumir(reserva.reserva_id, MENSAJE_1)
    with pytest.raises(EstadoInvalido):
        creditos.consumir(reserva.reserva_id, MENSAJE_2)


def test_liberar_devuelve_lo_pendiente_una_sola_vez() -> None:
    creditos = ReservaCreditosFalsa(saldo=5)
    reserva = reservar(creditos, 3)
    creditos.consumir(reserva.reserva_id, MENSAJE_1)
    assert creditos.liberar(reserva.reserva_id).liberados == 2
    assert creditos.liberar(reserva.reserva_id).liberados == 0
    assert creditos.reservado(ANA) == 0
    assert creditos.saldo(ANA) == 4


def test_una_reserva_inexistente_responde_no_encontrado() -> None:
    with pytest.raises(RecursoNoEncontrado):
        ReservaCreditosFalsa().liberar(MENSAJE_1)


class LanzarEjemplo:
    """Caso de uso de muestra: prueba que envio se escribe solo con los contratos."""

    def __init__(self, creditos: IReservaCreditos, uow: IUnidadDeTrabajo) -> None:
        self._creditos = creditos
        self._uow = uow
        self.encolados: list[IdPublico] = []

    def ejecutar(self, owner_id: IdPublico, campana_id: IdPublico, destinos: int) -> IdPublico:
        with self._uow as uow:
            resultado = self._creditos.reservar(owner_id, campana_id, destinos)
            if isinstance(resultado, ReservaRechazada):
                raise SaldoInsuficiente(
                    "Saldo insuficiente.", resultado.requerido, resultado.disponible
                )
            uow.al_confirmar(lambda: self.encolados.append(campana_id))
            return resultado.reserva_id


def test_un_lanzamiento_con_saldo_encola_tras_confirmar() -> None:
    caso = LanzarEjemplo(ReservaCreditosFalsa(saldo=2), UnidadDeTrabajoFalsa())
    caso.ejecutar(ANA, CAMPANA, 2)
    assert caso.encolados == [CAMPANA]


def test_un_lanzamiento_sin_saldo_no_encola() -> None:
    uow = UnidadDeTrabajoFalsa()
    caso = LanzarEjemplo(ReservaCreditosFalsa(saldo=1), uow)
    with pytest.raises(SaldoInsuficiente):
        caso.ejecutar(ANA, CAMPANA, 2)
    assert caso.encolados == []
    assert uow.reversiones == 1
