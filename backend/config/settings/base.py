"""Configuracion de la API v1. Hereda del sistema actual sin modificarlo."""

import os

from django.core.exceptions import ImproperlyConfigured

from core.settings import *  # noqa: F403

INSTALLED_APPS = [
    *INSTALLED_APPS,  # noqa: F405
    "rest_framework_simplejwt.token_blacklist",
    "masssend.infrastructure.persistence.identidad",
    "masssend.infrastructure.persistence.creditos",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

API_VERSION = "1.0.0"


def _opcion(variable: str, permitidas: tuple[str, ...], por_defecto: str) -> str:
    valor = os.environ.get(variable) or por_defecto
    if valor not in permitidas:
        raise ImproperlyConfigured(f"{variable} debe ser uno de {permitidas}.")
    return valor


# Cada variable elige un adaptador; la raiz de composicion las consume.
CANAL_MENSAJERIA = _opcion("CANAL_MENSAJERIA", ("whatsapp", "email", "fake"), "whatsapp")
COLA_ENVIOS = _opcion("COLA_ENVIOS", ("celery", "memoria", "sincrona"), "celery")
ALMACEN_ARCHIVOS = _opcion("ALMACEN_ARCHIVOS", ("pocketbase", "memoria"), "pocketbase")
GENERADOR_TEXTO = _opcion("GENERADOR_TEXTO", ("ollama", "fake"), "ollama")
PASARELA_PAGO_FAKE = _opcion("PASARELA_PAGO_FAKE", ("0", "1"), "0") == "1"
DESTINO_CORREO = _opcion("DESTINO_CORREO", ("gmail", "mailpit"), "gmail")
PROVEEDOR_GOOGLE = _opcion("PROVEEDOR_GOOGLE", ("google", "fake"), "google")
GOOGLE_RETORNO_V1 = (
    os.environ.get("GOOGLE_RETORNO_V1") or "http://localhost:8000/api/v1/auth/google/callback"
)

if DESTINO_CORREO == "mailpit":
    EMAIL_HOST = os.environ.get("MAILPIT_HOST", "mailpit")
    EMAIL_PORT = 1025
    EMAIL_USE_SSL = False
    EMAIL_USE_TLS = False
    # Sin contrasena, Django no intenta autenticarse contra Mailpit.
    EMAIL_HOST_USER = "masssend@prueba.local"
    EMAIL_HOST_PASSWORD = ""
    DEFAULT_FROM_EMAIL = EMAIL_HOST_USER

# Sin Redis se usa la cache en memoria del proceso.
REDIS_URL = os.environ.get("REDIS_URL")
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
        }
    }

# Solo se definen los limites: cada vista v1 activa sus clases, asi que las
# rutas actuales no cambian. NUM_PROXIES en 0 ignora X-Forwarded-For, que el
# cliente podria falsificar para evadir el limite.
REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # noqa: F405
    "NUM_PROXIES": 0,
    "DEFAULT_THROTTLE_RATES": {
        "anonimo_v1": os.environ.get("API_LIMITE_ANONIMO") or "60/min",
        "usuario_v1": os.environ.get("API_LIMITE_USUARIO") or "600/min",
        "sensible_v1": os.environ.get("API_LIMITE_SENSIBLE") or "10/min",
        "asistente_v1": os.environ.get("API_LIMITE_ASISTENTE") or "20/min",
    },
}
