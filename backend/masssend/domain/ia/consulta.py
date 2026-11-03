"""Consulta al asistente: limites del mensaje y del historial."""

from dataclasses import dataclass

from masssend.domain.shared.errores import DatosInvalidos

LONGITUD_MAXIMA = 2000
TURNOS_MAXIMOS = 6
LONGITUD_MAXIMA_TURNO = 500


@dataclass(frozen=True, slots=True)
class Turno:
    rol: str
    contenido: str


@dataclass(frozen=True, slots=True)
class Consulta:
    pregunta: str
    historial: tuple[Turno, ...]

    @classmethod
    def crear(cls, pregunta: str, historial: list[Turno]) -> "Consulta":
        limpia = pregunta.strip()
        if not limpia:
            raise DatosInvalidos("Escribe una pregunta para el asistente.", "pregunta")
        if len(limpia) > LONGITUD_MAXIMA:
            raise DatosInvalidos(
                f"La pregunta admite {LONGITUD_MAXIMA} caracteres como máximo.", "pregunta"
            )
        recientes = historial[-TURNOS_MAXIMOS:]
        recortes = tuple(Turno(t.rol, t.contenido[:LONGITUD_MAXIMA_TURNO]) for t in recientes)
        return cls(limpia, recortes)
