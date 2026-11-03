from django.apps import AppConfig


class EnvioConfig(AppConfig):
    name = "masssend.infrastructure.persistence.envio"
    label = "envio"
    default_auto_field = "django.db.models.BigAutoField"
