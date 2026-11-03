"""Lee el CSV de contactos fila a fila, sin cargar el archivo completo en memoria."""

import csv
import io
from collections.abc import Iterator
from typing import IO

from masssend.application.campanas.importacion import FilaImportacion
from masssend.domain.shared.errores import DatosInvalidos

SEPARADORES = {",": ",", ";": ";", "tab": "\t", "|": "|"}
COLUMNAS = {
    "telefono": ("telefono", "teléfono", "phone", "celular", "numero", "número"),
    "nombre": ("nombre", "name", "nombre completo"),
    "etiquetas": ("etiquetas", "tags", "etiqueta"),
    "notas": ("notas", "nota", "notes"),
}
# Sin encabezado se usa el orden del sistema actual.
ORDEN_POSICIONAL = {"telefono": 0, "nombre": 1, "etiquetas": 2, "notas": 3}


def _indices(encabezado: list[str]) -> dict[str, int]:
    normalizado = [columna.strip().lower() for columna in encabezado]
    indices: dict[str, int] = {}
    for campo, alias in COLUMNAS.items():
        for posicion, columna in enumerate(normalizado):
            if columna in alias:
                indices[campo] = posicion
                break
    if "telefono" not in indices:
        raise DatosInvalidos(
            "El encabezado debe tener una columna telefono. "
            "Si el archivo no tiene encabezado, envía encabezado=false.",
            "archivo",
        )
    return indices


class LectorCsv:
    """Valida el encabezado al crearse; las filas se leen bajo demanda."""

    def __init__(self, binario: IO[bytes], separador: str, encabezado: bool) -> None:
        if separador not in SEPARADORES:
            raise DatosInvalidos("Separador no soportado. Usa , ; tab o |.", "separador")
        texto = io.TextIOWrapper(binario, encoding="utf-8-sig", errors="replace", newline="")
        self._lector = csv.reader(texto, delimiter=SEPARADORES[separador])
        self._indices = ORDEN_POSICIONAL
        if encabezado:
            primera = next(self._lector, None)
            if primera is None:
                raise DatosInvalidos("El archivo está vacío.", "archivo")
            self._indices = _indices(primera)

    def filas(self) -> Iterator[FilaImportacion]:
        try:
            for fila in self._lector:
                if not any(celda.strip() for celda in fila):
                    continue
                yield FilaImportacion(
                    numero=self._lector.line_num,
                    telefono=self._celda(fila, "telefono"),
                    nombre=self._celda(fila, "nombre"),
                    etiquetas=self._celda(fila, "etiquetas"),
                    notas=self._celda(fila, "notas"),
                )
        except csv.Error as error:
            raise DatosInvalidos(
                f"El CSV está mal formado cerca de la fila {self._lector.line_num}.", "archivo"
            ) from error

    def _celda(self, fila: list[str], campo: str) -> str:
        posicion = self._indices.get(campo)
        if posicion is None or posicion >= len(fila):
            return ""
        return fila[posicion].strip()
