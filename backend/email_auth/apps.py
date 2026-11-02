from django.apps import AppConfig


class EmailAuthConfig(AppConfig):
    """
    App de MassSend encargada de todo lo relacionado a verificación de
    cuentas por correo (Gmail): registro con código OTP, reenvío de
    código, MFA (segundo factor tipo Authenticator), recuperación de
    contraseña y envío de notificaciones/adjuntos por correo mediante
    una cola interna.

    Está separada del app "mass_sender" a propósito (principio de
    responsabilidad única / SRP): mass_sender se encarga de WhatsApp,
    email_auth se encarga exclusivamente de correo + identidad.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "email_auth"
    verbose_name = "Verificación de Correo (MFA / Recuperación)"
