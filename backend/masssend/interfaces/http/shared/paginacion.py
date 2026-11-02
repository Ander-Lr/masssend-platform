"""Traduce la paginacion del dominio a parametros y respuestas HTTP."""

from collections.abc import Callable
from typing import Any, TypeVar

from rest_framework.request import Request
from rest_framework.response import Response

from masssend.domain.shared.errores import DatosInvalidos
from masssend.domain.shared.paginacion import (
    LIMITE_POR_DEFECTO,
    Cursor,
    Pagina,
    PeticionPagina,
)

T = TypeVar("T")


def peticion_pagina(request: Request) -> PeticionPagina:
    limite = request.query_params.get("limite", LIMITE_POR_DEFECTO)
    cursor = request.query_params.get("cursor")
    try:
        limite_entero = int(limite)
    except ValueError as error:
        raise DatosInvalidos("El limite debe ser un numero.", "limite") from error
    return PeticionPagina(
        limite=limite_entero,
        cursor=Cursor.decodificar(cursor) if cursor else None,
    )


def respuesta_pagina(pagina: Pagina[T], serializar: Callable[[T], dict[str, Any]]) -> Response:
    siguiente = pagina.siguiente_cursor
    return Response(
        {
            "datos": [serializar(elemento) for elemento in pagina.elementos],
            "pagina": {
                "siguiente_cursor": siguiente.codificar() if siguiente else None,
                "tiene_mas": pagina.tiene_mas,
            },
        }
    )
