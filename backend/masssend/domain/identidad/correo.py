"""Normalizacion y validacion del correo, trasladada de email_auth/utils/text.py."""

import re

from masssend.domain.shared.errores import DatosInvalidos

_PATRON = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def normalizar_correo(correo: str) -> str:
    return correo.strip().lower()


def validar_correo(correo: str) -> str:
    normalizado = normalizar_correo(correo)
    if not _PATRON.match(normalizado):
        raise DatosInvalidos("El formato del correo es incorrecto.", "correo")
    return normalizado
