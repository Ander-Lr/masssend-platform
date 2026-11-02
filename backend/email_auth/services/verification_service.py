"""
Registro de cuentas + verificación por código OTP enviado a Gmail.
Equivalente Django de `verification.service.js`.

Nunca llama a Gmail directamente: solo encola la tarea en EmailTask.
El envío real lo hace el comando `process_email_queue` (el worker).
"""
from django.conf import settings
from django.utils import timezone

from ..models import EmailTask, SecurityProfile
from ..repositories import queue_repository, user_repository
from ..utils.codes import generate_verification_code
from ..utils.errors import AppError
from ..utils.passwords import hash_password
from ..utils.text import is_valid_email, normalize_email


def _expires_at():
    return timezone.now() + timezone.timedelta(minutes=settings.EMAIL_CODE_TTL_MINUTES)


def _public_user(user, profile: SecurityProfile) -> dict:
    return {
        "id": user.id,
        "name": user.get_full_name() or user.first_name or user.username,
        "email": user.email,
        "status": profile.status,
        "mfaEnabled": bool(profile.mfa_enabled),
        "isStaff": bool(user.is_staff),
        "createdAt": user.date_joined.isoformat(),
        "updatedAt": profile.updated_at.isoformat() if profile.updated_at else None,
    }


def register_user(*, name: str, email: str, password: str) -> dict:
    clean_name = (name or "").strip()
    normalized_email = normalize_email(email)
    clean_password = (password or "").strip()

    if not clean_name or not normalized_email:
        raise AppError("El nombre y el correo son obligatorios.", 400)

    if not is_valid_email(normalized_email):
        raise AppError("El formato del correo electrónico es incorrecto.", 400)

    if not clean_password or len(clean_password) < 6:
        raise AppError("La contraseña es obligatoria y debe tener al menos 6 caracteres.", 400)

    existing_user, existing_profile = user_repository.find_by_email(normalized_email)
    if existing_profile and existing_profile.status == SecurityProfile.STATUS_ACTIVE:
        raise AppError("La cuenta ya se encuentra activa.", 409)

    verification_code = generate_verification_code()
    expires_at = _expires_at()

    user, profile = user_repository.create_pending_user(
        name=clean_name,
        email=normalized_email,
        password_hash=hash_password(clean_password),
        verification_code=verification_code,
        expires_at=expires_at,
    )

    task = queue_repository.enqueue(
        task_type=EmailTask.TYPE_ACCOUNT_VERIFICATION,
        recipient=user.email,
        subject="Código de activación de cuenta",
        message=f"Código de verificación para {user.email}",
        payload={"name": clean_name, "email": user.email, "code": verification_code},
    )

    return {
        "message": "Cuenta registrada como inactiva. El código de verificación se encoló y se enviará en un momento.",
        "user": _public_user(user, profile),
        "codeExpiresAt": expires_at.isoformat(),
        "taskId": str(task.id),
    }


def verify_account(*, email: str, code: str) -> dict:
    normalized_email = normalize_email(email)
    clean_code = (code or "").strip()

    if not normalized_email or not clean_code:
        raise AppError("El correo y el código son obligatorios.", 400)

    user, profile = user_repository.find_by_email(normalized_email)
    if not user:
        raise AppError("No existe una cuenta registrada con ese correo.", 404)

    if profile.status == SecurityProfile.STATUS_ACTIVE:
        return {"message": "La cuenta ya se encuentra activa.", "user": _public_user(user, profile)}

    if not profile.verification_code_expires_at or profile.verification_code_expires_at < timezone.now():
        raise AppError("El código ha expirado. Solicita el reenvío de un nuevo código.", 400)

    if profile.verification_attempts >= settings.EMAIL_MAX_VERIFICATION_ATTEMPTS:
        raise AppError("Se alcanzó el número máximo de intentos. Solicita un nuevo código.", 429)

    if profile.verification_code != clean_code:
        profile.verification_attempts += 1
        profile.save(update_fields=["verification_attempts", "updated_at"])
        remaining = max(settings.EMAIL_MAX_VERIFICATION_ATTEMPTS - profile.verification_attempts, 0)
        raise AppError(f"El código es incorrecto. Intentos restantes: {remaining}.", 400)

    user, profile = user_repository.activate_user(user, profile)

    return {"message": "Cuenta activada correctamente.", "user": _public_user(user, profile)}


def get_account_status(email: str) -> dict:
    normalized_email = normalize_email(email)
    user, profile = user_repository.find_by_email(normalized_email)
    if not user:
        raise AppError("La cuenta no se encuentra registrada.", 404)
    return {"user": _public_user(user, profile)}


def resend_verification_code(email: str) -> dict:
    normalized_email = normalize_email(email)
    user, profile = user_repository.find_by_email(normalized_email)
    if not user:
        raise AppError("La cuenta no se encuentra registrada.", 404)

    if profile.status == SecurityProfile.STATUS_ACTIVE:
        raise AppError("La cuenta ya se encuentra activa.", 409)

    verification_code = generate_verification_code()
    expires_at = _expires_at()

    user_repository.update_profile(
        profile,
        verification_code=verification_code,
        verification_code_expires_at=expires_at,
        verification_attempts=0,
    )

    task = queue_repository.enqueue(
        task_type=EmailTask.TYPE_RESEND_VERIFICATION_CODE,
        recipient=user.email,
        subject="Reenvío del código de activación",
        message=f"Reenvío de código para {user.email}",
        payload={
            "name": user.get_full_name() or user.first_name or user.username,
            "email": user.email,
            "code": verification_code,
        },
    )

    return {
        "message": "Se encoló el reenvío de un nuevo código de verificación. Revisa tu correo en un momento.",
        "codeExpiresAt": expires_at.isoformat(),
        "taskId": str(task.id),
    }
