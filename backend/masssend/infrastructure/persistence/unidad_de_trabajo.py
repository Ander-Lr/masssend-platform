from collections.abc import Callable
from types import TracebackType
from typing import Self

from django.db import transaction


class UnidadDeTrabajoDjango:
    """Unico lugar del sistema que abre transacciones."""

    def __init__(self) -> None:
        self._atomico = transaction.atomic()

    def __enter__(self) -> Self:
        self._atomico.__enter__()
        return self

    def __exit__(
        self,
        tipo: type[BaseException] | None,
        error: BaseException | None,
        traza: TracebackType | None,
    ) -> None:
        self._atomico.__exit__(tipo, error, traza)

    def al_confirmar(self, accion: Callable[[], None]) -> None:
        transaction.on_commit(accion)
