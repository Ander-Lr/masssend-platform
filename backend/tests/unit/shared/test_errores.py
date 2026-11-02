import pytest

from masssend.domain.shared import errores
from masssend.domain.shared.errores import (
    DatosInvalidos,
    DemasiadosIntentos,
    ErrorDominio,
    SaldoInsuficiente,
)


def test_cada_error_tiene_un_codigo_propio() -> None:
    clases = [
        c
        for c in vars(errores).values()
        if isinstance(c, type) and issubclass(c, ErrorDominio) and c is not ErrorDominio
    ]
    assert len(clases) == 8
    assert len({c.codigo for c in clases}) == len(clases)


def test_los_errores_conservan_el_detalle() -> None:
    assert DatosInvalidos("mal", "nombre").campo == "nombre"
    assert DemasiadosIntentos("espera", 30).espera_segundos == 30
    saldo = SaldoInsuficiente("falta", requerido=5, disponible=2)
    assert (saldo.requerido, saldo.disponible) == (5, 2)


def test_se_pueden_capturar_como_error_de_dominio() -> None:
    with pytest.raises(ErrorDominio) as error:
        raise DatosInvalidos("mal", "nombre")
    assert error.value.mensaje == "mal"
