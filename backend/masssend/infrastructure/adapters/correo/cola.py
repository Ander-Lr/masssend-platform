"""Reutiliza la cola, el worker y las plantillas actuales de correo."""

from urllib.parse import urlencode

from email_auth.models import EmailTask


class ColaEmailTask:
    def __init__(self, url_frontend: str) -> None:
        self._url_frontend = url_frontend

    def encolar_verificacion(self, nombre: str, correo: str, codigo: str) -> None:
        EmailTask.objects.create(
            task_type=EmailTask.TYPE_ACCOUNT_VERIFICATION,
            recipient=correo,
            subject="Código de activación de cuenta",
            message=f"Código de verificación para {correo}",
            payload={"name": nombre, "email": correo, "code": codigo},
        )

    def encolar_recuperacion(self, nombre: str, correo: str, token: str, minutos: int) -> None:
        consulta = urlencode({"token": token, "email": correo})
        EmailTask.objects.create(
            task_type=EmailTask.TYPE_PASSWORD_RECOVERY,
            recipient=correo,
            subject="Recuperación de tu cuenta",
            message=f"Enlace de recuperación para {correo}",
            payload={
                "name": nombre,
                "email": correo,
                "resetUrl": f"{self._url_frontend}/reset-password?{consulta}",
                "expirationMinutes": minutos,
            },
        )
