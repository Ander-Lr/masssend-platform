import uuid

from django.conf import settings
from django.db import models


class SecurityProfile(models.Model):
    """
    Datos de seguridad de un usuario relacionados con la verificación de
    correo y el MFA. Se guarda aparte de auth.User (en vez de agregarle
    campos) para no tocar el modelo de usuario que ya usan Google OAuth
    y el login clásico de Masssend (Open/Closed: extendemos sin modificar).
    """

    STATUS_INACTIVE = "INACTIVE"
    STATUS_ACTIVE = "ACTIVE"
    STATUS_CHOICES = [
        (STATUS_INACTIVE, "Inactiva (pendiente de verificación)"),
        (STATUS_ACTIVE, "Activa"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="security_profile",
        verbose_name="Usuario",
    )

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_INACTIVE,
        verbose_name="Estado de la cuenta",
    )

    # ── Verificación de correo (OTP de 6 dígitos) ──────────────────────
    verification_code = models.CharField(max_length=6, blank=True, null=True)
    verification_code_expires_at = models.DateTimeField(blank=True, null=True)
    verification_attempts = models.PositiveIntegerField(default=0)
    activated_at = models.DateTimeField(blank=True, null=True)

    # ── MFA (segundo factor tipo Google/Microsoft Authenticator) ──────
    mfa_enabled = models.BooleanField(default=False, verbose_name="¿MFA activo?")
    mfa_secret = models.CharField(max_length=64, blank=True, null=True)
    pending_mfa_secret = models.CharField(max_length=64, blank=True, null=True)

    # ── Recuperación de contraseña ─────────────────────────────────────
    recovery_token = models.CharField(max_length=128, blank=True, null=True)
    recovery_token_expires_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "email_auth_security_profile"
        verbose_name = "Perfil de seguridad"
        verbose_name_plural = "Perfiles de seguridad"

    def __str__(self):
        return f"{self.user.email or self.user.username} ({self.status})"


class EmailTask(models.Model):
    """
    Cola interna de correos pendientes de enviar. Las vistas/servicios
    NUNCA llaman a Gmail directamente: solo encolan una fila aquí con
    estado PENDING. El comando de administración
    `process_email_queue` (el "worker") es el único lugar que envía
    correos de verdad y mueve el estado a PROCESSING -> SENT/FAILED.
    """

    TYPE_ACCOUNT_VERIFICATION = "ACCOUNT_VERIFICATION"
    TYPE_RESEND_VERIFICATION_CODE = "RESEND_VERIFICATION_CODE"
    TYPE_PASSWORD_RECOVERY = "PASSWORD_RECOVERY"
    TYPE_CUSTOM_NOTIFICATION = "CUSTOM_NOTIFICATION"
    TYPE_ATTACHMENT_NOTIFICATION = "ATTACHMENT_NOTIFICATION"
    TYPE_CHOICES = [
        (TYPE_ACCOUNT_VERIFICATION, "Verificación de cuenta"),
        (TYPE_RESEND_VERIFICATION_CODE, "Reenvío de código"),
        (TYPE_PASSWORD_RECOVERY, "Recuperación de contraseña"),
        (TYPE_CUSTOM_NOTIFICATION, "Notificación personalizada"),
        (TYPE_ATTACHMENT_NOTIFICATION, "Notificación con adjunto"),
    ]

    STATUS_PENDING = "PENDING"
    STATUS_PROCESSING = "PROCESSING"
    STATUS_SENT = "SENT"
    STATUS_FAILED = "FAILED"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pendiente"),
        (STATUS_PROCESSING, "Procesando"),
        (STATUS_SENT, "Enviado"),
        (STATUS_FAILED, "Fallido"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task_type = models.CharField(max_length=40, choices=TYPE_CHOICES)
    recipient = models.EmailField()
    subject = models.CharField(max_length=200)
    message = models.CharField(max_length=255, blank=True)
    payload = models.JSONField(default=dict, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    attempts = models.PositiveIntegerField(default=0)
    error = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "email_auth_email_task"
        verbose_name = "Tarea de correo"
        verbose_name_plural = "Cola de correos"
        ordering = ["created_at"]

    def __str__(self):
        return f"[{self.status}] {self.task_type} -> {self.recipient}"


class QueueControl(models.Model):
    """
    Fila única (singleton) usada para pausar/reanudar la cola desde el
    panel de administración o la API, igual que `pauseQueue`/`resumeQueue`
    en la práctica original.
    """

    paused = models.BooleanField(default=False)

    class Meta:
        db_table = "email_auth_queue_control"
        verbose_name = "Control de la cola"
        verbose_name_plural = "Control de la cola"

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def __str__(self):
        return "Pausada" if self.paused else "Activa"
