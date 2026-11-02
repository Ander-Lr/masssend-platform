"""
Repositorio de usuarios + su perfil de seguridad.

Los servicios (verification_service, mfa_service, recovery_service)
solo hablan con estas funciones, nunca con el ORM directamente. Así,
si mañana se cambia el modelo de datos (o se usa otra fuente de
usuarios), solo hay que tocar este archivo (principio de inversión de
dependencias / DIP y de responsabilidad única / SRP).
"""
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from ..models import SecurityProfile


def find_by_email(email: str):
    """
    Devuelve (User, SecurityProfile) o (None, None) si no existe.

    Si el usuario existía antes de este módulo (creado por Google OAuth
    o por un administrador) y todavía no tiene SecurityProfile, se crea
    uno reflejando su estado real (`is_active`) en vez de asumir
    "inactivo": de lo contrario, un usuario legítimo y activo quedaría
    bloqueado de usar MFA solo por no haberse registrado por este flujo.
    """
    user = User.objects.filter(username=email).select_related("security_profile").first()
    if not user:
        return None, None
    profile, _ = SecurityProfile.objects.get_or_create(
        user=user,
        defaults={
            "status": SecurityProfile.STATUS_ACTIVE if user.is_active else SecurityProfile.STATUS_INACTIVE,
        },
    )
    return user, profile


@transaction.atomic
def create_pending_user(*, name: str, email: str, password_hash: str, verification_code: str, expires_at):
    """
    Crea (o reutiliza, si estaba INACTIVE) un usuario con is_active=False
    hasta que verifique su correo. El username y el email son siempre
    el mismo correo, igual que en el login con Google.
    """
    first_name, *rest = (name.split(" ") if name else [""])
    last_name = " ".join(rest)

    user, created = User.objects.get_or_create(
        username=email,
        defaults={
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "is_active": False,
        },
    )

    if not created:
        user.first_name = first_name or user.first_name
        user.last_name = last_name or user.last_name
        user.is_active = False

    user.password = password_hash
    user.save()

    profile, _ = SecurityProfile.objects.get_or_create(user=user)
    profile.status = SecurityProfile.STATUS_INACTIVE
    profile.verification_code = verification_code
    profile.verification_code_expires_at = expires_at
    profile.verification_attempts = 0
    profile.save()

    return user, profile


def update_profile(profile: SecurityProfile, **changes):
    for field, value in changes.items():
        setattr(profile, field, value)
    profile.save()
    return profile


def activate_user(user: User, profile: SecurityProfile):
    user.is_active = True
    user.save(update_fields=["is_active"])

    profile.status = SecurityProfile.STATUS_ACTIVE
    profile.verification_code = None
    profile.verification_code_expires_at = None
    profile.verification_attempts = 0
    profile.activated_at = timezone.now()
    profile.save()
    return user, profile


def set_password(user: User, password_hash: str):
    user.password = password_hash
    user.save(update_fields=["password"])
    return user
