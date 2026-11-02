from django.urls import path

from .views import auth_views, mfa_views, notification_views, queue_views, recovery_views

app_name = "email_auth"

urlpatterns = [
    # ── Registro y verificación de cuenta ──────────────────────────────
    path("auth/register/", auth_views.register, name="register"),
    path("auth/verify/", auth_views.verify, name="verify"),
    path("auth/resend/", auth_views.resend, name="resend"),
    path("auth/status/<str:email>/", auth_views.status, name="status"),

    # ── Login con MFA ──────────────────────────────────────────────────
    path("auth/login-step1/", mfa_views.login_step1, name="login_step1"),
    path("auth/login-step2/", mfa_views.login_step2, name="login_step2"),
    path("auth/google-mfa-verify/", mfa_views.google_login_verify, name="google_mfa_verify"),

    # ── Configuración de MFA ────────────────────────────────────────────
    path("mfa/setup/", mfa_views.setup, name="mfa_setup"),
    path("mfa/confirm/", mfa_views.confirm, name="mfa_confirm"),
    path("mfa/status/", mfa_views.status, name="mfa_status"),
    path("mfa/disable/", mfa_views.disable, name="mfa_disable"),

    # ── Recuperación de contraseña ──────────────────────────────────────
    path("auth/recover/", recovery_views.request_recovery, name="recover"),
    path("auth/validate-token/", recovery_views.validate_token, name="validate_token"),
    path("auth/reset-password/", recovery_views.reset_password, name="reset_password"),

    # ── Notificaciones ───────────────────────────────────────────────────
    path("notifications/send/", notification_views.send_notification, name="notification_send"),
    path("notifications/attachment/", notification_views.send_attachment, name="notification_attachment"),

    # ── Cola de correos (admin) ──────────────────────────────────────────
    path("queue/tasks/", queue_views.list_tasks, name="queue_tasks"),
    path("queue/pause/", queue_views.pause_queue, name="queue_pause"),
    path("queue/resume/", queue_views.resume_queue, name="queue_resume"),
]
