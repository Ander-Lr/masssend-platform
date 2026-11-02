"""Recuperación de contraseña por enlace enviado a Gmail (equivalente de recovery.service.js)."""
from django.conf import settings
from django.utils import timezone

from ..models import EmailTask
from ..repositories import queue_repository, user_repository
from ..utils.codes import generate_recovery_token
from ..utils.errors import AppError
from ..utils.passwords import hash_password
from ..utils.text import is_valid_email, normalize_email

RECOVERY_TOKEN_TTL_MINUTES = 15


def _build_reset_url(*, token: str, email: str) -> str:
    from urllib.parse import urlencode
    query = urlencode({"token": token, "email": email})
    return f"{settings.FRONTEND_URL}/reset-password?{query}"


def _mask_token(token: str) -> str:
    if not token or len(token) < 8:
        return "********"
    return f"{token[:4]}...{token[-4:]}"


def request_account_recovery(email: str) -> dict:
    normalized_email = normalize_email(email)

    if not normalized_email or not is_valid_email(normalized_email):
        raise AppError("Debes indicar un correo electrónico válido.", 400)

    user, profile = user_repository.find_by_email(normalized_email)
    if not user:
        raise AppError("No existe una cuenta registrada con ese correo.", 404)

    token = generate_recovery_token()
    expires_at = timezone.now() + timezone.timedelta(minutes=RECOVERY_TOKEN_TTL_MINUTES)

    user_repository.update_profile(profile, recovery_token=token, recovery_token_expires_at=expires_at)

    reset_url = _build_reset_url(token=token, email=normalized_email)

    task = queue_repository.enqueue(
        task_type=EmailTask.TYPE_PASSWORD_RECOVERY,
        recipient=normalized_email,
        subject="Recuperación de tu cuenta",
        message=f"Enlace de recuperación para {normalized_email}",
        payload={
            "name": user.get_full_name() or user.first_name or user.username,
            "email": normalized_email,
            "resetUrl": reset_url,
            "expirationMinutes": RECOVERY_TOKEN_TTL_MINUTES,
        },
    )

    return {
        "message": "Se registró la solicitud de recuperación. El correo se enviará en un momento.",
        "taskId": str(task.id),
        "tokenPreview": _mask_token(token),
        "tokenExpiresAt": expires_at.isoformat(),
    }


def _assert_valid_token(profile, token: str):
    if not profile or not profile.recovery_token:
        raise AppError("No hay una recuperación pendiente para esta cuenta.", 400)

    if profile.recovery_token != token:
        raise AppError("El token de recuperación es inválido.", 400)

    if not profile.recovery_token_expires_at or profile.recovery_token_expires_at < timezone.now():
        raise AppError("El token de recuperación venció. Solicita el enlace nuevamente.", 400)


def validate_recovery_token(*, email: str, token: str) -> dict:
    normalized_email = normalize_email(email)
    clean_token = (token or "").strip()
    _, profile = user_repository.find_by_email(normalized_email)

    _assert_valid_token(profile, clean_token)

    return {"message": "El token es válido.", "email": normalized_email}


def reset_password(*, email: str, token: str, new_password: str) -> dict:
    normalized_email = normalize_email(email)
    clean_token = (token or "").strip()
    clean_password = (new_password or "").strip()

    user, profile = user_repository.find_by_email(normalized_email)
    _assert_valid_token(profile, clean_token)

    if not clean_password or len(clean_password) < 6:
        raise AppError("La nueva contraseña debe tener al menos 6 caracteres.", 400)

    user_repository.set_password(user, hash_password(clean_password))
    user_repository.update_profile(profile, recovery_token=None, recovery_token_expires_at=None)

    return {"message": "La contraseña se actualizó correctamente. Ya puedes iniciar sesión."}
