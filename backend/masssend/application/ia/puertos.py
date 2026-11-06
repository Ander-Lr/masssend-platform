from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class MensajeChat:
    """rol es system, user o assistant, como en las API de chat."""

    rol: str
    contenido: str


@dataclass(frozen=True, slots=True)
class TextoGenerado:
    texto: str
    modelo: str
    # False si el modelo se quedo sin espacio y corto la respuesta a mitad.
    completo: bool = True


@dataclass(frozen=True, slots=True)
class EstadoGenerador:
    disponible: bool
    modelo: str
    modelo_descargado: bool


class IGeneradorTexto(Protocol):
    def generar(self, mensajes: list[MensajeChat]) -> TextoGenerado:
        """Lanza ServicioNoDisponible si el modelo no responde."""
        ...

    def estado(self) -> EstadoGenerador: ...
