"""Puertos base. El nucleo nunca toca el reloj, el azar ni la base directamente."""

from collections.abc import Callable
from datetime import datetime
from types import TracebackType
from typing import Protocol, Self

from masssend.domain.shared.identificadores import IdPublico


class IReloj(Protocol):
    def ahora(self) -> datetime:
        """Devuelve el instante actual, siempre con zona horaria."""
        ...


class IGeneradorIds(Protocol):
    def nuevo(self) -> IdPublico:
        """Devuelve un UUIDv7 nuevo."""
        ...


class IAleatorio(Protocol):
    def token(self, longitud: int) -> str:
        """Devuelve un texto seguro para URL, de la longitud indicada."""
        ...

    def digitos(self, cantidad: int) -> str:
        """Devuelve un codigo numerico, por ejemplo para verificar correos."""
        ...


class IUnidadDeTrabajo(Protocol):
    """Transaccion: confirma al salir bien del with y revierte ante una excepcion."""

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        tipo: type[BaseException] | None,
        error: BaseException | None,
        traza: TracebackType | None,
    ) -> None: ...

    def al_confirmar(self, accion: Callable[[], None]) -> None:
        """Agenda un efecto externo; solo se ejecuta si la transaccion confirma."""
        ...


class IComprobadorDependencia(Protocol):
    """Revisa un servicio. Si es requerido y falla, la API no esta disponible."""

    nombre: str
    requerida: bool

    def comprobar(self) -> bool: ...
