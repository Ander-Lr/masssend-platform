"""Paginacion por cursor: estable aunque entren filas nuevas."""

import base64
import binascii
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Generic, TypeVar

from masssend.domain.shared.errores import DatosInvalidos

LIMITE_POR_DEFECTO = 20
LIMITE_MAXIMO = 100

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class Cursor:
    """Valores de la ultima fila entregada. El cliente lo trata como opaco."""

    valores: tuple[str, ...]

    def codificar(self) -> str:
        crudo = json.dumps(list(self.valores), separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(crudo).decode().rstrip("=")

    @classmethod
    def decodificar(cls, texto: str) -> "Cursor":
        relleno = "=" * (-len(texto) % 4)
        try:
            datos = json.loads(base64.urlsafe_b64decode(texto + relleno))
        except (binascii.Error, ValueError) as error:
            raise DatosInvalidos("El cursor no es valido.", "cursor") from error
        if not isinstance(datos, list) or not all(isinstance(v, str) for v in datos):
            raise DatosInvalidos("El cursor no es valido.", "cursor")
        return cls(tuple(datos))


@dataclass(frozen=True, slots=True)
class PeticionPagina:
    limite: int = LIMITE_POR_DEFECTO
    cursor: Cursor | None = None

    def __post_init__(self) -> None:
        if not 1 <= self.limite <= LIMITE_MAXIMO:
            raise DatosInvalidos(f"El limite debe estar entre 1 y {LIMITE_MAXIMO}.", "limite")


@dataclass(frozen=True, slots=True)
class Pagina(Generic[T]):
    elementos: tuple[T, ...]
    siguiente_cursor: Cursor | None = None

    @property
    def tiene_mas(self) -> bool:
        return self.siguiente_cursor is not None

    @classmethod
    def desde_filas(
        cls,
        filas: Sequence[T],
        peticion: PeticionPagina,
        cursor_de: Callable[[T], Cursor],
    ) -> "Pagina[T]":
        """Arma la pagina. El repositorio debe pedir limite + 1 filas."""
        elementos = tuple(filas[: peticion.limite])
        if len(filas) <= peticion.limite:
            return cls(elementos)
        return cls(elementos, cursor_de(elementos[-1]))
