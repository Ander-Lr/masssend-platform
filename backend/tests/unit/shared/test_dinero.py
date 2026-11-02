from decimal import Decimal

import pytest

from masssend.domain.shared.dinero import Dinero
from masssend.domain.shared.errores import DatosInvalidos


def test_opera_sin_errores_de_redondeo() -> None:
    assert Dinero.desde_decimal("0.10").sumar(Dinero.desde_decimal("0.20")) == Dinero(30)
    assert Dinero(30).como_decimal() == Decimal("0.30")
    assert Dinero(250).multiplicar(3) == Dinero(750)
    assert Dinero(750).restar(Dinero(250)) == Dinero(500)


@pytest.mark.parametrize("monto", ["1.999", "abc", "NaN", "Infinity", "-1"])
def test_rechaza_montos_invalidos(monto: str) -> None:
    with pytest.raises(DatosInvalidos):
        Dinero.desde_decimal(monto)


def test_no_queda_en_negativo() -> None:
    with pytest.raises(DatosInvalidos):
        Dinero(100).restar(Dinero(101))


def test_no_mezcla_monedas() -> None:
    with pytest.raises(DatosInvalidos):
        Dinero(100, "USD").sumar(Dinero(100, "EUR"))


@pytest.mark.parametrize("moneda", ["usd", "US", "US1"])
def test_exige_moneda_valida(moneda: str) -> None:
    with pytest.raises(DatosInvalidos):
        Dinero(100, moneda)
