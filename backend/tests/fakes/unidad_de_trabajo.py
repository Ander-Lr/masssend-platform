from collections.abc import Callable
from types import TracebackType
from typing import Self


class UnidadDeTrabajoFalsa:
    """Se comporta como una transaccion, sin base de datos."""

    def __init__(self) -> None:
        self.confirmaciones = 0
        self.reversiones = 0
        self._acciones: list[Callable[[], None]] = []

    def __enter__(self) -> Self:
        self._acciones = []
        return self

    def __exit__(
        self,
        tipo: type[BaseException] | None,
        error: BaseException | None,
        traza: TracebackType | None,
    ) -> None:
        if tipo is not None:
            self.reversiones += 1
            self._acciones = []
            return
        self.confirmaciones += 1
        acciones, self._acciones = self._acciones, []
        for accion in acciones:
            accion()

    def al_confirmar(self, accion: Callable[[], None]) -> None:
        self._acciones.append(accion)
