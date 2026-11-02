import pytest

from masssend.domain.shared.errores import DatosInvalidos
from masssend.domain.shared.paginacion import Cursor, Pagina, PeticionPagina


def cursor_de(fila: int) -> Cursor:
    return Cursor((str(fila),))


def test_el_cursor_va_y_vuelve() -> None:
    cursor = Cursor(("2026-01-01", "campaña"))
    assert Cursor.decodificar(cursor.codificar()) == cursor


@pytest.mark.parametrize("texto", ["%%%", "e30", "WzFd", "bm8tanNvbg"])
def test_rechaza_cursores_manipulados(texto: str) -> None:
    with pytest.raises(DatosInvalidos) as error:
        Cursor.decodificar(texto)
    assert error.value.campo == "cursor"


@pytest.mark.parametrize("limite", [0, -1, 101])
def test_limita_el_tamano_de_pagina(limite: int) -> None:
    with pytest.raises(DatosInvalidos):
        PeticionPagina(limite=limite)


def test_con_mas_filas_recorta_y_entrega_cursor() -> None:
    pagina = Pagina.desde_filas([1, 2, 3], PeticionPagina(limite=2), cursor_de)
    assert pagina.elementos == (1, 2)
    assert pagina.tiene_mas
    assert pagina.siguiente_cursor == cursor_de(2)


def test_la_ultima_pagina_no_tiene_cursor() -> None:
    pagina = Pagina.desde_filas([1, 2], PeticionPagina(limite=2), cursor_de)
    assert pagina.elementos == (1, 2)
    assert not pagina.tiene_mas
