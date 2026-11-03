"""Las mismas reglas que normalizar_telefono, ahora como objeto de valor."""

import pytest

from masssend.domain.campanas.telefono import Telefono
from masssend.domain.shared.errores import DatosInvalidos


@pytest.mark.parametrize(
    ("crudo", "esperado"),
    [
        ("099 111-2222", "593991112222"),
        ("0991112222", "593991112222"),
        ("+593 99 111 2222", "593991112222"),
        ("593991112222", "593991112222"),
        ("  (099) 111.2222  ", "593991112222"),
        ("+57 300 123 4567", "573001234567"),
        ("+1 (305) 555-0100", "13055550100"),
        ("123456789012345", "123456789012345"),
    ],
)
def test_normaliza_a_e164_sin_signo(crudo: str, esperado: str) -> None:
    assert Telefono.desde_texto(crudo).numero == esperado


@pytest.mark.parametrize(
    ("crudo", "fragmento"),
    [
        ("", "vacío"),
        ("   ", "vacío"),
        ("1.3071E+12", "notación científica"),
        ("099abc2222", "demasiado corto"),
        ("593+991112222", "caracteres inválidos"),
        ("022345678", "fijo"),
        ("59322345678", "fijo de Ecuador"),
        ("59399111222", "Móvil Ecuador inválido"),
        ("5939911122223", "Móvil Ecuador inválido"),
        ("3001234567", "demasiado corto"),
        ("1234567890123456", "demasiado largo"),
        ("+", "caracteres inválidos"),
    ],
)
def test_rechaza_lo_que_no_es_un_movil(crudo: str, fragmento: str) -> None:
    with pytest.raises(DatosInvalidos) as error:
        Telefono.desde_texto(crudo)
    assert error.value.campo == "telefono"
    assert fragmento in error.value.mensaje


def test_dos_escrituras_del_mismo_numero_son_iguales() -> None:
    a = Telefono.desde_texto("099 111 2222")
    b = Telefono.desde_texto("+593991112222")
    assert a == b
    assert len({a, b}) == 1
    assert str(a) == "593991112222"


def test_es_inmutable() -> None:
    telefono = Telefono.desde_texto("0991112222")
    with pytest.raises(AttributeError):
        telefono.numero = "593990000000"  # type: ignore[misc]


@pytest.mark.parametrize("numero", ["0991112222", "+593991112222", "12"])
def test_el_constructor_exige_un_numero_ya_normalizado(numero: str) -> None:
    with pytest.raises(DatosInvalidos):
        Telefono(numero)
