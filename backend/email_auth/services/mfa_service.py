"""
Autenticación en dos pasos (MFA/2FA) tipo Google/Microsoft Authenticator.

Equivalente Django de `mfa.service.js`, pero usando `pyotp` (TOTP) en
vez de `@otplib/preset-default`, y la librería `qrcode` para generar
la imagen del código QR como data URL (igual que hace `qrcode` en
Node).

Nota de diseño: aquí NO se llama a `django.contrib.auth.login()`
porque eso requiere el objeto `request`, que es un detalle HTTP. Las
funciones de login devuelven el `User` autenticado (o None) y es la
vista quien decide iniciar la sesión (separación de responsabilidades
entre lógica de negocio y capa HTTP).
"""
import base64
from io import BytesIO

import pyotp
import qrcode
from django.conf import settings
from django.contrib.auth import authenticate

from ..models import SecurityProfile
from ..repositories import user_repository
from ..utils.errors import AppError
from ..utils.text import normalize_email


def _public_mfa_user(user, profile: SecurityProfile) -> dict:
    return {
        "id": user.id,
        "name": user.get_full_name() or user.first_name or user.username,
        "email": user.email,
        "status": profile.status,
        "mfaEnabled": bool(profile.mfa_enabled),
        "isStaff": bool(user.is_staff),
    }


def _get_active_user(user):
    user, profile = user_repository.find_by_email(user.username)

    if profile.status != SecurityProfile.STATUS_ACTIVE:
        raise AppError("La cuenta debe estar activa antes de usar autenticación en dos pasos.", 403)

    return user, profile


def _build_qr_data_url(otpauth_uri: str) -> str:
    image = qrcode.make(otpauth_uri)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def start_mfa_setup(user) -> dict:
    user, profile = _get_active_user(user)

    if profile.mfa_enabled:
        raise AppError("La autenticación en dos pasos ya está activada para esta cuenta.", 409)

    secret = pyotp.random_base32()
    otpauth_uri = pyotp.totp.TOTP(secret).provisioning_uri(
        name=user.email, issuer_name=settings.MFA_ISSUER,
    )
    qr_code = _build_qr_data_url(otpauth_uri)

    user_repository.update_profile(profile, pending_mfa_secret=secret)

    return {
        "message": "Escanea el código QR con Google Authenticator o Microsoft Authenticator.",
        "email": user.email,
        "issuer": settings.MFA_ISSUER,
        "manualKey": secret,
        "qrCode": qr_code,
    }


def confirm_mfa_setup(*, user, code: str) -> dict:
    user, profile = _get_active_user(user)
    clean_code = (code or "").replace(" ", "")

    if not profile.pending_mfa_secret:
        raise AppError("No existe una configuración MFA pendiente para esta cuenta.", 400)

    if not clean_code:
        raise AppError("El código del autenticador es obligatorio.", 400)

    totp = pyotp.TOTP(profile.pending_mfa_secret)
    if not totp.verify(clean_code, valid_window=settings.MFA_WINDOW):
        raise AppError(
            "El código ingresado no es válido. Revisa la hora del celular o espera un nuevo código.", 400,
        )

    user_repository.update_profile(
        profile, mfa_enabled=True, mfa_secret=profile.pending_mfa_secret, pending_mfa_secret=None,
    )

    return {"message": "Autenticación en dos pasos activada correctamente.", "user": _public_mfa_user(user, profile)}


def login_first_step(*, email: str, password: str):
    """
    Verifica el primer factor y devuelve el usuario junto con el siguiente
    paso requerido. La vista conserva una sesión breve hasta que MFA quede
    activado o se valide el código TOTP.
    """
    raw_identifier = (email or "").strip()
    normalized_email = normalize_email(email)

    # Django's authenticate() ya rechaza usuarios con is_active=False,
    # así que no hace falta (ni conviene) volver a chequear el estado
    # aquí. Se intenta primero tal cual lo escribió el usuario (para no
    # romper usuarios/administradores creados antes de este módulo,
    # cuyo username puede no ser un correo y sí importarle mayúsculas),
    # y si falla se reintenta ya normalizado (correo en minúsculas),
    # que es como quedan guardadas las cuentas nuevas de email_auth.
    user = authenticate(username=raw_identifier, password=password or "")
    if not user and normalized_email != raw_identifier:
        user = authenticate(username=normalized_email, password=password or "")

    if not user:
        raise AppError("Correo o contraseña incorrectos.", 401)

    _, profile = user_repository.find_by_email(user.username)

    if not profile.mfa_enabled:
        return user, {
            "message": "La cuenta debe activar MFA antes de continuar.",
            "requiresMfaEnrollment": True,
            "email": user.email or user.username,
        }

    return user, {
        "message": "Primer factor correcto. Ingresa el código del autenticador.",
        "requiresMfa": True,
        "email": user.email or user.username,
    }


def verify_mfa_login(*, user, code: str):
    user, profile = _get_active_user(user)
    clean_code = (code or "").replace(" ", "")

    if not profile.mfa_enabled or not profile.mfa_secret:
        raise AppError("La cuenta no tiene autenticación en dos pasos activada.", 400)

    if not clean_code:
        raise AppError("El código MFA es obligatorio.", 400)

    totp = pyotp.TOTP(profile.mfa_secret)
    if not totp.verify(clean_code, valid_window=settings.MFA_WINDOW):
        raise AppError("El código MFA no es válido o ya venció.", 400)

    return user, {"message": "Inicio de sesión completado con segundo factor.", "user": _public_mfa_user(user, profile)}


def get_mfa_status(user) -> dict:
    user, profile = _get_active_user(user)
    return {"user": _public_mfa_user(user, profile)}


def disable_mfa(*, user, password: str) -> dict:
    """
    Desactiva el MFA de la cuenta. Se exige la contraseña (no solo el
    correo) para confirmar que quien apaga el 2FA es realmente el
    dueño de la cuenta, no solo alguien con la sesión abierta.
    """
    user, profile = _get_active_user(user)

    if not profile.mfa_enabled:
        raise AppError("La cuenta no tiene autenticación en dos pasos activada.", 400)

    if not user.check_password(password or ""):
        raise AppError("Contraseña incorrecta.", 401)

    user_repository.update_profile(profile, mfa_enabled=False, mfa_secret=None, pending_mfa_secret=None)

    return {
        "message": "Autenticación en dos pasos desactivada correctamente.",
        "user": _public_mfa_user(user, profile),
    }
