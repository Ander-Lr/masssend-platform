"""Entidad Campana y su maquina de estados.

    borrador ──iniciar──> en_curso ──completar──> completada
       │                     │
       └──────cancelar───────┴──────────────────> cancelada

Solo un borrador se modifica. Una campana en curso no se elimina: primero
se cancela, para que sus creditos reservados se liberen.
"""

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum

from masssend.domain.campanas.contacto import limpiar_etiquetas
from masssend.domain.shared.errores import DatosInvalidos, EstadoInvalido
from masssend.domain.shared.identificadores import IdPublico

MAX_NOMBRE = 150
# Limite de un mensaje de texto de WhatsApp.
MAX_MENSAJE = 4096
NOMBRE_POR_DEFECTO = "Amigo"
_VARIABLE = re.compile(r"\{\{\s*(\w+)\s*\}\}")


class EstadoCampana(StrEnum):
    BORRADOR = "borrador"
    EN_CURSO = "en_curso"
    COMPLETADA = "completada"
    CANCELADA = "cancelada"


TRANSICIONES: dict[EstadoCampana, frozenset[EstadoCampana]] = {
    EstadoCampana.BORRADOR: frozenset({EstadoCampana.EN_CURSO, EstadoCampana.CANCELADA}),
    EstadoCampana.EN_CURSO: frozenset({EstadoCampana.COMPLETADA, EstadoCampana.CANCELADA}),
    EstadoCampana.COMPLETADA: frozenset(),
    EstadoCampana.CANCELADA: frozenset(),
}


def _limpiar_nombre(nombre: str) -> str:
    limpio = nombre.strip()
    if not limpio:
        raise DatosInvalidos("El nombre de la campaña es obligatorio.", "nombre")
    if len(limpio) > MAX_NOMBRE:
        raise DatosInvalidos(f"El nombre no puede superar {MAX_NOMBRE} caracteres.", "nombre")
    return limpio


def _limpiar_mensaje(mensaje: str) -> str:
    limpio = mensaje.strip()
    if not limpio:
        raise DatosInvalidos("El mensaje es obligatorio.", "mensaje")
    if len(limpio) > MAX_MENSAJE:
        raise DatosInvalidos(f"El mensaje no puede superar {MAX_MENSAJE} caracteres.", "mensaje")
    return limpio


def personalizar(plantilla: str, nombre: str, datos: Mapping[str, str] | None = None) -> str:
    """Reemplaza {{nombre}} y las variables propias del contacto.

    Una variable que el contacto no tiene queda tal cual, como en el sistema actual.
    """
    valores = {**(datos or {}), "nombre": nombre.strip() or NOMBRE_POR_DEFECTO}

    def reemplazar(coincidencia: re.Match[str]) -> str:
        return valores.get(coincidencia.group(1), coincidencia.group(0))

    return _VARIABLE.sub(reemplazar, plantilla)


@dataclass
class Campana:
    id: IdPublico
    owner_id: IdPublico
    nombre: str
    mensaje: str
    etiquetas: tuple[str, ...] = ()
    estado: EstadoCampana = EstadoCampana.BORRADOR
    adjunto: str | None = None

    @classmethod
    def nueva(
        cls,
        id: IdPublico,
        owner_id: IdPublico,
        nombre: str,
        mensaje: str,
        etiquetas: str | Iterable[str] = (),
    ) -> "Campana":
        return cls(
            id,
            owner_id,
            _limpiar_nombre(nombre),
            _limpiar_mensaje(mensaje),
            limpiar_etiquetas(etiquetas),
        )

    def pertenece_a(self, owner_id: IdPublico) -> bool:
        return self.owner_id == owner_id

    @property
    def es_borrador(self) -> bool:
        return self.estado is EstadoCampana.BORRADOR

    def exigir_borrador(self) -> None:
        if not self.es_borrador:
            raise EstadoInvalido(f"Solo se modifica un borrador; la campaña está {self.estado}.")

    def editar(
        self,
        nombre: str | None = None,
        mensaje: str | None = None,
        etiquetas: str | Iterable[str] | None = None,
    ) -> None:
        """Valida todo antes de cambiar algo."""
        self.exigir_borrador()
        nuevo_nombre = self.nombre if nombre is None else _limpiar_nombre(nombre)
        nuevo_mensaje = self.mensaje if mensaje is None else _limpiar_mensaje(mensaje)
        nuevas = self.etiquetas if etiquetas is None else limpiar_etiquetas(etiquetas)
        self.nombre, self.mensaje, self.etiquetas = nuevo_nombre, nuevo_mensaje, nuevas

    def adjuntar(self, referencia: str) -> None:
        self.exigir_borrador()
        self.adjunto = referencia

    def quitar_adjunto(self) -> None:
        self.exigir_borrador()
        self.adjunto = None

    def mensaje_para(self, nombre: str, datos: Mapping[str, str] | None = None) -> str:
        return personalizar(self.mensaje, nombre, datos)

    def _pasar_a(self, destino: EstadoCampana) -> None:
        if destino not in TRANSICIONES[self.estado]:
            raise EstadoInvalido(f"Una campaña {self.estado} no puede pasar a {destino}.")
        self.estado = destino

    def iniciar(self) -> None:
        self._pasar_a(EstadoCampana.EN_CURSO)

    def completar(self) -> None:
        self._pasar_a(EstadoCampana.COMPLETADA)

    def cancelar(self) -> None:
        self._pasar_a(EstadoCampana.CANCELADA)

    def exigir_eliminable(self) -> None:
        if self.estado is EstadoCampana.EN_CURSO:
            raise EstadoInvalido("Cancela la campaña antes de eliminarla.")
