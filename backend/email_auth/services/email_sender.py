"""
Envío de correo puro (sin lógica de negocio). Define una interfaz
(`EmailSender`) y una implementación concreta con Gmail vía SMTP
(`DjangoSmtpEmailSender`) que usa el backend de correo de Django
(configurado en settings.py con EMAIL_HOST=smtp.gmail.com).

Los servicios de negocio (verification_service, recovery_service...)
dependen únicamente de la interfaz, nunca de smtplib directamente
(principio de inversión de dependencias / DIP). Esto permite, por
ejemplo, cambiar a otro proveedor de correo sin tocar el resto del
código, o inyectar un "fake" sender en pruebas.
"""
from abc import ABC, abstractmethod

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection

from ..email_templates.custom_message_email import create_custom_message_email
from ..email_templates.recovery_email import create_recovery_email
from ..email_templates.verification_email import create_verification_email


class EmailSender(ABC):
    @abstractmethod
    def send_email(self, *, to, subject, text, html, attachments=None):
        raise NotImplementedError

    def send_verification_email(self, *, name, email, code):
        message = create_verification_email(
            name=name, code=code, expiration_minutes=settings.EMAIL_CODE_TTL_MINUTES,
        )
        return self.send_email(to=email, subject=message["subject"], text=message["text"], html=message["html"])

    def send_recovery_email(self, *, name, email, reset_url, expiration_minutes):
        message = create_recovery_email(name=name, reset_url=reset_url, expiration_minutes=expiration_minutes)
        return self.send_email(to=email, subject=message["subject"], text=message["text"], html=message["html"])

    def send_custom_message(self, *, to, subject, title, message, signature):
        content = create_custom_message_email(title=title, message=message, signature=signature)
        return self.send_email(to=to, subject=subject, text=content["text"], html=content["html"])

    def send_attachment_email(self, *, to, subject, title, message, signature, attachment):
        content = create_custom_message_email(title=title, message=message, signature=signature)
        return self.send_email(
            to=to, subject=subject, text=content["text"], html=content["html"],
            attachments=[attachment],
        )


class DjangoSmtpEmailSender(EmailSender):
    """
    Implementación real: usa el backend SMTP de Django, configurado en
    settings.py a partir de las variables de entorno EMAIL_USER /
    EMAIL_APP_PASSWORD (la misma cuenta de Gmail usada en la práctica).
    """

    def send_email(self, *, to, subject, text, html, attachments=None):
        connection = get_connection()
        message = EmailMultiAlternatives(
            subject=subject,
            body=text,
            from_email=f"MassSend <{settings.EMAIL_HOST_USER}>",
            to=[to],
            connection=connection,
        )
        message.attach_alternative(html, "text/html")

        for attachment in attachments or []:
            # attachment: {"filename": str, "contentBase64" | "content": bytes, "mimeType": str}
            # (mismas claves camelCase que usa el payload de EmailTask)
            content = attachment.get("content")
            if content is None:
                import base64
                content = base64.b64decode(attachment["contentBase64"])
            message.attach(attachment["filename"], content, attachment.get("mimeType"))

        return message.send()


# Instancia única compartida por los servicios (equivalente al
# `transporter` exportado por mail.config.js).
default_email_sender: EmailSender = DjangoSmtpEmailSender()
