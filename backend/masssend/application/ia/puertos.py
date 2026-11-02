from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class TextoGenerado:
    texto: str
    modelo: str


@dataclass(frozen=True, slots=True)
class EstadoGenerador:
    disponible: bool
    modelo: str
    modelo_descargado: bool


class IGeneradorTexto(Protocol):
    def generar(self, prompt: str) -> TextoGenerado:
        """Lanza ServicioNoDisponible si el modelo no responde."""
        ...

    def estado(self) -> EstadoGenerador: ...
