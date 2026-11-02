"""Reglas de seguridad de la identidad."""

from datetime import timedelta

from masssend.domain.shared.errores import DatosInvalidos

LONGITUD_MINIMA_CONTRASENA = 8
MAX_INTENTOS_VERIFICACION = 5
MAX_FALLOS_TOTP = 5
BLOQUEO_TOTP = timedelta(minutes=15)
VIGENCIA_DESAFIO_LOGIN = timedelta(minutes=5)
VIGENCIA_DESAFIO_ENROLAMIENTO = timedelta(minutes=15)
VIGENCIA_RECUPERACION = timedelta(minutes=15)
VIGENCIA_ESTADO_GOOGLE = timedelta(minutes=10)


def validar_contrasena(contrasena: str, campo: str = "contrasena") -> None:
    if len(contrasena) < LONGITUD_MINIMA_CONTRASENA:
        raise DatosInvalidos(
            f"La contraseña debe tener al menos {LONGITUD_MINIMA_CONTRASENA} caracteres.", campo
        )
