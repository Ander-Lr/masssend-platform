from django.apps import AppConfig


class BillingConfig(AppConfig):
    """
    App de MassSend encargada de la monetización: catálogo de paquetes
    de créditos, cobro con PayPal/PayPhone, y la billetera de créditos
    que se descuenta al ejecutar campañas de envío masivo.

    Elegimos "créditos por mensaje enviado" (en vez de una suscripción
    mensual) porque encaja mejor con lo que ya existe en mass_sender
    (una campaña = N contactos = N mensajes) y porque las dos pasarelas
    adaptadas de la práctica (PayPal Orders API, PayPhone Links API)
    solo soportan cobros únicos, no pagos recurrentes.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "billing"
    verbose_name = "Facturación (créditos y pagos)"
