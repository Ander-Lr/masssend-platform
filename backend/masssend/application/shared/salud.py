"""Caso de uso: informar el estado de la API y sus dependencias."""

from collections.abc import Sequence
from dataclasses import dataclass

from masssend.application.shared.puertos import IComprobadorDependencia

OK = "ok"
DEGRADADO = "degradado"
CAIDO = "caido"


@dataclass(frozen=True, slots=True)
class ResultadoSalud:
    estado: str
    version: str
    dependencias: dict[str, str]

    @property
    def disponible(self) -> bool:
        return self.estado != CAIDO


class ComprobarSalud:
    def __init__(self, dependencias: Sequence[IComprobadorDependencia], version: str) -> None:
        self._dependencias = dependencias
        self._version = version

    def ejecutar(self) -> ResultadoSalud:
        estados: dict[str, str] = {}
        estado = OK
        for dependencia in self._dependencias:
            responde = dependencia.comprobar()
            estados[dependencia.nombre] = OK if responde else CAIDO
            if not responde:
                estado = CAIDO if dependencia.requerida else _peor(estado, DEGRADADO)
        return ResultadoSalud(estado, self._version, estados)


def _peor(actual: str, nuevo: str) -> str:
    return actual if actual == CAIDO else nuevo
