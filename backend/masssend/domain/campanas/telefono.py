"""Objeto de valor Telefono, trasladado de normalizar_telefono en mass_sender/services.py.

Se guarda en formato E.164 sin el signo +. Las reglas se conservan:
- Movil de Ecuador 09XXXXXXXX se convierte en 5939XXXXXXXX.
- Los fijos de Ecuador se rechazan porque no reciben WhatsApp.
- Un numero de otro pais necesita su codigo: entre 11 y 15 digitos.
"""

import re
from dataclasses import dataclass

from masssend.domain.shared.errores import DatosInvalidos

CAMPO = "telefono"
_NOTACION_CIENTIFICA = re.compile(r"[Ee][+\-]?\d")
_NO_DIGITOS = re.compile(r"[^\d+]")
_LOCAL_ECUADOR = re.compile(r"^0\d{7,9}$")
_E164 = re.compile(r"^\d{11,15}$")
MINIMO_DIGITOS = 11
MAXIMO_DIGITOS = 15
DIGITOS_MOVIL_ECUADOR = 12


def _invalido(mensaje: str) -> DatosInvalidos:
    return DatosInvalidos(mensaje, CAMPO)


def _normalizar(crudo: str) -> str:
    texto = crudo.strip()
    if not texto:
        raise _invalido("Teléfono vacío")
    if _NOTACION_CIENTIFICA.search(texto):
        raise _invalido("Número en notación científica — revisa el formato del CSV")
    limpio = _NO_DIGITOS.sub("", texto).removeprefix("+")
    if not limpio.isdigit():
        raise _invalido("Teléfono contiene caracteres inválidos")
    if _LOCAL_ECUADOR.match(limpio):
        sin_cero = limpio[1:]
        if not sin_cero.startswith("9"):
            raise _invalido(
                f"Número fijo ({limpio[:3]}...) — los fijos no reciben WhatsApp. "
                "Los móviles ecuatorianos empiezan con 09XXXXXXXX."
            )
        limpio = "593" + sin_cero
    if limpio.startswith("593"):
        if not limpio.startswith("5939"):
            raise _invalido(
                f"Número fijo de Ecuador ({limpio[:5]}...) — "
                "los fijos no reciben WhatsApp. Solo móviles 5939XXXXXXXX."
            )
        if len(limpio) != DIGITOS_MOVIL_ECUADOR:
            raise _invalido(
                f"Móvil Ecuador inválido: {len(limpio)} dígitos "
                "(se esperan exactamente 12: 5939XXXXXXXX)."
            )
        return limpio
    if len(limpio) < MINIMO_DIGITOS:
        raise _invalido(
            f"Número demasiado corto ({len(limpio)} dígitos). "
            "Para Ecuador usa 09XXXXXXXX. "
            "Para otros países incluye el código de país (ej: 573... Colombia, 1... EEUU)."
        )
    if len(limpio) > MAXIMO_DIGITOS:
        raise _invalido(f"Número demasiado largo ({len(limpio)} dígitos, máximo 15).")
    return limpio


@dataclass(frozen=True, slots=True)
class Telefono:
    """Numero ya normalizado. Dos telefonos son iguales si sus digitos lo son."""

    numero: str

    def __post_init__(self) -> None:
        if not _E164.match(self.numero):
            raise _invalido("El teléfono debe estar normalizado en formato E.164 sin +.")

    @classmethod
    def desde_texto(cls, crudo: str) -> "Telefono":
        """Limpia lo que escribe el usuario o trae el CSV. Lanza DatosInvalidos."""
        return cls(_normalizar(crudo))

    def __str__(self) -> str:
        return self.numero
