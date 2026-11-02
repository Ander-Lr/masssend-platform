from django.urls import path
from . import views
from . import ai_views

app_name = 'mass_sender'

urlpatterns = [
    # ── Asistente IA local (Ollama) ───────────────────────────────────────
    path('api/asistente/chat/', ai_views.api_asistente_chat, name='api_asistente_chat'),
    path('api/asistente/health/', ai_views.api_asistente_health, name='api_asistente_health'),

    # ── Webhooks internos autenticados (llamados por Node.js) ─────────────
    path('api/webhook/', views.api_webhook, name='api_webhook'),
    path('api/message-ack/', views.api_message_ack, name='api_message_ack'),
    path('api/send-result/', views.api_send_result, name='api_send_result'),

    # ── Chat del panel (solo staff) ───────────────────────────────────────
    path('api/chat/mensajes/', views.api_leer_mensajes, name='api_leer_mensajes'),
    path('api/chat/enviar/', views.api_enviar_whatsapp, name='api_enviar_whatsapp'),

    # ── WhatsApp conexión ─────────────────────────────────────────────────
    path('api/qr-status/', views.api_qr_status, name='api_qr_status'),
    path('api/cambiar-numero/', views.api_cambiar_numero, name='api_cambiar_numero'),
    path('api/request-pairing/', views.api_request_pairing, name='api_request_pairing'),

    # ── Reportes ──────────────────────────────────────────────────────────
    path('api/reportes/', views.api_reportes, name='api_reportes'),
    path('reportes/', views.reportes_view, name='reportes'),

    # ── Progreso campaña ──────────────────────────────────────────────────
    path('api/campaign-progress/<int:campaign_id>/', views.api_campaign_progress, name='api_campaign_progress'),
    path('monitor/<int:campaign_id>/', views.campaign_monitor_view, name='campaign_monitor'),

    # ── Importar contactos (admin Django) ─────────────────────────────────
    path('import-contacts/', views.import_contacts, name='import_contacts'),

    # ── API REST para React ───────────────────────────────────────────────

    # Autenticación
    path('api/auth/logout/', views.api_logout, name='api_logout'),
    path('api/auth/me/', views.api_me, name='api_me'),

    # Campañas
    path('api/campanas/', views.api_campanas_list, name='api_campanas_list'),
    path('api/campanas/<int:pk>/', views.api_campanas_detail, name='api_campanas_detail'),
    path('api/campanas/<int:pk>/ejecutar/', views.api_campanas_ejecutar, name='api_campanas_ejecutar'),
    path('api/campanas/<int:pk>/media/', views.api_campanas_media, name='api_campanas_media'),

    # Contactos
    path('api/contactos/', views.api_contactos_list, name='api_contactos_list'),
    path('api/contactos/importar/', views.api_contactos_importar, name='api_contactos_importar'),
    path('api/contactos/bulk-delete/', views.api_contactos_bulk_delete, name='api_contactos_bulk_delete'),
    path('api/contactos/<int:pk>/', views.api_contactos_detail, name='api_contactos_detail'),

    # Mensajes
    path('api/mensajes/', views.api_mensajes_list, name='api_mensajes_list'),
    path('api/mensajes/bulk-delete/', views.api_mensajes_bulk_delete, name='api_mensajes_bulk_delete'),
]
