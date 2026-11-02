import pytest

from masssend.domain.creditos.billetera import Billetera
from masssend.domain.creditos.reserva import Reserva
from masssend.domain.shared.errores import (
    DatosInvalidos,
    EstadoInvalido,
    SaldoInsuficiente,
)
from tests.fakes.ids import GeneradorIdsSecuencial

IDS = GeneradorIdsSecuencial()
ANA = IDS.nuevo()


def test_reservar_aparta_sin_tocar_el_saldo() -> None:
    billetera = Billetera(ANA, 10)
    assert billetera.reservar(4)
    assert (billetera.saldo, billetera.reservado, billetera.disponible) == (10, 4, 6)


def test_no_se_reserva_mas_de_lo_disponible() -> None:
    billetera = Billetera(ANA, 5, reservado=4)
    assert not billetera.reservar(2)
    assert billetera.reservado == 4


@pytest.mark.parametrize("cantidad", [0, -1])
def test_las_cantidades_deben_ser_positivas(cantidad: int) -> None:
    with pytest.raises(DatosInvalidos):
        Billetera(ANA, 5).reservar(cantidad)
    with pytest.raises(DatosInvalidos):
        Billetera(ANA, 5).acreditar(cantidad)


def test_consumir_baja_saldo_y_reservado() -> None:
    billetera = Billetera(ANA, 5, reservado=2)
    billetera.consumir()
    assert (billetera.saldo, billetera.reservado) == (4, 1)


def test_no_se_consume_sin_reserva() -> None:
    with pytest.raises(EstadoInvalido):
        Billetera(ANA, 5).consumir()


def test_si_el_sistema_actual_gasto_el_saldo_no_queda_negativo() -> None:
    billetera = Billetera(ANA, 0, reservado=1)
    with pytest.raises(SaldoInsuficiente):
        billetera.consumir()
    assert billetera.saldo == 0


def test_lo_disponible_nunca_se_informa_negativo() -> None:
    assert Billetera(ANA, 1, reservado=3).disponible == 0


def test_liberar_devuelve_lo_reservado() -> None:
    billetera = Billetera(ANA, 5, reservado=3)
    billetera.liberar(2)
    assert billetera.disponible == 4


def test_no_se_libera_mas_de_lo_reservado() -> None:
    with pytest.raises(EstadoInvalido):
        Billetera(ANA, 5, reservado=1).liberar(2)


def test_acreditar_suma_al_saldo() -> None:
    billetera = Billetera(ANA, 5)
    billetera.acreditar(10)
    assert billetera.saldo == 15


@pytest.mark.parametrize(("saldo", "reservado"), [(-1, 0), (1, -1)])
def test_nunca_nace_en_negativo(saldo: int, reservado: int) -> None:
    with pytest.raises(EstadoInvalido):
        Billetera(ANA, saldo, reservado)


def test_la_reserva_no_baja_de_cero() -> None:
    reserva = Reserva(IDS.nuevo(), ANA, IDS.nuevo(), 1, 1)
    reserva.consumir()
    with pytest.raises(EstadoInvalido):
        reserva.consumir()


def test_liberar_la_reserva_una_sola_vez() -> None:
    reserva = Reserva(IDS.nuevo(), ANA, IDS.nuevo(), 3, 2)
    assert reserva.liberar() == 2
    assert reserva.liberar() == 0
