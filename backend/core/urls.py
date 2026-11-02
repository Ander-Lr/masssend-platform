"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from mass_sender import views as ms_views
from mass_sender import auth_views

admin.site.site_header = 'MassSend - Panel de Control'
admin.site.site_title = 'MassSend Admin'
admin.site.index_title = 'Gestión de Mensajería'

urlpatterns = [
    path('admin/import-contacts/', admin.site.admin_view(ms_views.import_contacts), name='admin_import_contacts'),
    path('admin/cambiar-numero/', admin.site.admin_view(ms_views.cambiar_numero_admin_view), name='admin_cambiar_numero'),
    path('admin/', admin.site.urls),
    path('whatsapp/', include('mass_sender.urls')),
    # Verificación de correo (Gmail), MFA y recuperación de contraseña
    path('api/email-auth/', include('email_auth.urls')),
    # Créditos y pasarelas de pago (PayPal + PayPhone)
    path('api/billing/', include('billing.urls')),
    path('api/csrf/', auth_views.csrf_cookie, name='csrf_cookie'),
    # Google OAuth 2.0 + JWT
    path('auth/google/', auth_views.google_login, name='google_login'),
    path('auth/google/callback/', auth_views.google_callback, name='google_callback'),
    path('auth/perfil/', auth_views.perfil_usuario, name='perfil_usuario'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
