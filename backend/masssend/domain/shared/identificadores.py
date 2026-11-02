"""Identificadores publicos: todo ID expuesto por la API es UUIDv7."""

from typing import NewType
from uuid import UUID

from masssend.domain.shared.errores import DatosInvalidos

IdPublico = NewType("IdPublico", UUID)


def id_publico(valor: UUID | str, campo: str = "id") -> IdPublico:
    """Convierte y valida un identificador; rechaza lo que no sea UUIDv7."""
    try:
        identificador = valor if isinstance(valor, UUID) else UUID(valor)
    except ValueError as error:
        raise DatosInvalidos("El identificador no es valido.", campo) from error
    if identificador.version != 7:
        raise DatosInvalidos("El identificador debe ser UUIDv7.", campo)
    return IdPublico(identificador)
