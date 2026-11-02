"""
Django settings for core project.
"""

import os
from pathlib import Path
import dj_database_url
from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured

load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# ── Unfold Admin Theme ────────────────────────────────────────────
UNFOLD = {
    "SITE_TITLE": "MassSend",
    "SITE_HEADER": "MassSend — Sistema de Mensajería",
    "SIDEBAR": {
        "navigation": [
            {
                "title": "Mensajería",
                "items": [
                    {
                        "title": "Contactos",
                        "link": "/admin/mass_sender/contact/",
                        "icon": "person",
                    },
                    {
                        "title": "Campañas",
                        "link": "/admin/mass_sender/campaign/",
                        "icon": "campaign",
                    },
                    {
                        "title": "Mensajes",
                        "link": "/admin/mass_sender/message/",
                        "icon": "chat",
                    },
                ],
            },
            {
                "title": "Herramientas",
                "items": [
                    {
                        "title": "Importar Contactos CSV",
                        "link": "/admin/import-contacts/",
                        "icon": "upload_file",
                    },
                    {
                        "title": "Cambiar Número WhatsApp",
                        "link": "/admin/cambiar-numero/",
                        "icon": "phonelink_setup",
                    },
                ],
            },
        ]
    },
}


# ── Seguridad ─────────────────────────────────────────────────────
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    raise ImproperlyConfigured('Configura SECRET_KEY fuera del repositorio antes de iniciar Django.')

DEBUG = os.environ.get('DEBUG', 'False') == 'True'

ALLOWED_HOSTS_ENV = os.environ.get('ALLOWED_HOSTS', '')
ALLOWED_HOSTS = [h.strip() for h in ALLOWED_HOSTS_ENV.split(',') if h.strip()] if ALLOWED_HOSTS_ENV else ['localhost', '127.0.0.1', 'backend']

# CSRF para Railway (proxy HTTPS)
CSRF_TRUSTED_ORIGINS = [
    'https://*.railway.app',
    'https://*.up.railway.app',
]
CSRF_ORIGINS_ENV = os.environ.get('CSRF_TRUSTED_ORIGINS', '')
if CSRF_ORIGINS_ENV:
    CSRF_TRUSTED_ORIGINS += [o.strip() for o in CSRF_ORIGINS_ENV.split(',') if o.strip()]

if not DEBUG and '*' in ALLOWED_HOSTS:
    raise ImproperlyConfigured('ALLOWED_HOSTS no puede contener * cuando DEBUG está desactivado.')

SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_CONTENT_TYPE_NOSNIFF = True


# ── Aplicaciones ──────────────────────────────────────────────────
INSTALLED_APPS = [
    'unfold',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'rest_framework',
    'rest_framework_simplejwt',
    'mass_sender',
    'email_auth',
    'billing',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'mass_sender.middleware.JWTAuthMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

LANGUAGE_CODE = 'es-es'

# ── CORS: permitir peticiones desde React ─────────────────────────
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'global_templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'


# ── Base de datos ─────────────────────────────────────────────────
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=600,
            ssl_require=os.environ.get('DB_SSL_REQUIRE', 'False' if DEBUG else 'True') == 'True',
        )
    }
else:
    # SQLITE_PATH permite ubicar la base en un volumen de Docker Swarm
    # (una sola instancia de BD compartida, requisito del clúster).
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': os.environ.get('SQLITE_PATH', BASE_DIR / 'db.sqlite3'),
        }
    }


# ── Validadores de contraseña ─────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# ── Internacionalización ──────────────────────────────────────────
LANGUAGE_CODE = 'es-es'
TIME_ZONE = 'America/Lima'
USE_I18N = True
USE_TZ = True


# ── Archivos estáticos ────────────────────────────────────────────
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

# ── Media (archivos subidos) ──────────────────────────────────────
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ── Clave primaria por defecto ────────────────────────────────────
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ── Servicio WhatsApp API (Node.js) ───────────────────────────────
WHATSAPP_API_URL = os.environ.get('WHATSAPP_API_URL', 'http://localhost:3000')

# ── Modelo de IA local (Ollama) — asistente de MassSend ───────────
# Comunicación síncrona (RPC sobre HTTP) con el modelo servido por
# Ollama, según lo visto en clase (ollama-rpc-practica).
OLLAMA_URL = os.environ.get('OLLAMA_URL', 'http://localhost:11434')
OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL', 'qwen2.5:0.5b')
OLLAMA_TIMEOUT_SECONDS = int(os.environ.get('OLLAMA_TIMEOUT_SECONDS', '60'))

# ── PocketBase — almacenamiento de fotos/videos de campañas ───────
# Según lo visto en clase (pocketbase-storage): los archivos viven en
# un servicio de almacenamiento independiente; Django guarda la URL.
POCKETBASE_URL = os.environ.get('POCKETBASE_URL', 'http://localhost:8090')
# URL interna que usa el gateway para descargar los archivos.
POCKETBASE_PUBLIC_URL = os.environ.get('POCKETBASE_PUBLIC_URL', POCKETBASE_URL)
POCKETBASE_COLLECTION = os.environ.get('POCKETBASE_COLLECTION', 'campaign_media')
POCKETBASE_ADMIN_EMAIL = os.environ.get('POCKETBASE_ADMIN_EMAIL', 'admin@masssend.local')
POCKETBASE_ADMIN_PASSWORD = os.environ.get('POCKETBASE_ADMIN_PASSWORD', '')
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'http://localhost:5173')

# Secreto compartido únicamente entre Django y el gateway dentro de la red privada.
WHATSAPP_WEBHOOK_TOKEN = os.environ.get('WHATSAPP_WEBHOOK_TOKEN', '')

# ── Correo (Gmail) — verificación de cuenta / MFA / recuperación ──
# Reutiliza la misma cuenta y contraseña de aplicación validadas en
# la práctica "practica-verificacion-gmail" (smtp.gmail.com:465 SSL).
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 465
EMAIL_USE_SSL = True
EMAIL_USE_TLS = False
EMAIL_HOST_USER = os.environ.get('EMAIL_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_APP_PASSWORD', '').replace(' ', '')
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER

EMAIL_CODE_TTL_MINUTES = int(os.environ.get('EMAIL_CODE_TTL_MINUTES', '5'))
EMAIL_MAX_VERIFICATION_ATTEMPTS = int(os.environ.get('EMAIL_MAX_VERIFICATION_ATTEMPTS', '5'))
EMAIL_QUEUE_MAX_ATTEMPTS = int(os.environ.get('EMAIL_MAX_QUEUE_ATTEMPTS', '3'))
EMAIL_QUEUE_INTERVAL_MS = int(os.environ.get('EMAIL_QUEUE_INTERVAL_MS', '5000'))
EMAIL_MAX_ATTACHMENT_SIZE_MB = int(os.environ.get('EMAIL_MAX_ATTACHMENT_SIZE_MB', '20'))

# MFA (TOTP tipo Google/Microsoft Authenticator)
MFA_ISSUER = os.environ.get('MFA_ISSUER', 'MassSend')
MFA_WINDOW = int(os.environ.get('MFA_WINDOW', '1'))

# ── Pasarelas de pago (créditos) ──────────────────────────────────
PAYPAL_CLIENT_ID = os.environ.get('PAYPAL_CLIENT_ID', '')
PAYPAL_CLIENT_SECRET = os.environ.get('PAYPAL_CLIENT_SECRET', '')
PAYPAL_BASE_URL = os.environ.get('PAYPAL_BASE_URL', 'https://api-m.sandbox.paypal.com')

PAYPHONE_TOKEN = os.environ.get('PAYPHONE_TOKEN', '')
PAYPHONE_STORE_ID = os.environ.get('PAYPHONE_STORE_ID', '')
PAYPHONE_BASE_URL = os.environ.get('PAYPHONE_BASE_URL', 'https://pay.payphonetodoesposible.com')

# Créditos gratis de bienvenida (se otorgan una sola vez, al crear la
# billetera del usuario, para que pueda probar el sistema antes de
# comprar más).
FREE_SIGNUP_CREDITS = int(os.environ.get('FREE_SIGNUP_CREDITS', '10'))

# ── Google OAuth 2.0 ──────────────────────────────────────────────
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')
GOOGLE_REDIRECT_URI = os.environ.get('GOOGLE_REDIRECT_URI', 'http://localhost:5173/auth/google/callback/')

# ── JWT - djangorestframework-simplejwt ───────────────────────────
from datetime import timedelta

JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY')
if not JWT_SECRET_KEY:
    raise ImproperlyConfigured('Configura JWT_SECRET_KEY independiente de SECRET_KEY.')

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=8),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': JWT_SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
}

# ── Logging ───────────────────────────────────────────────────────
# La carpeta de logs debe existir antes de configurar el FileHandler
# (en Docker la imagen se construye sin ella).
(BASE_DIR / 'logs').mkdir(exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{asctime}] {levelname} {name}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'masssend.log',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'mass_sender': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}
