from django.urls import path

from masssend.interfaces.http.identidad import vistas as v

urlpatterns = [
    path("auth/registro", v.RegistroVista.as_view()),
    path("auth/verificar", v.VerificarVista.as_view()),
    path("auth/reenviar-codigo", v.ReenviarCodigoVista.as_view()),
    path("auth/login", v.LoginVista.as_view()),
    path("auth/login/totp", v.LoginTotpVista.as_view()),
    path("auth/token/renovar", v.RenovarVista.as_view()),
    path("auth/logout", v.LogoutVista.as_view()),
    path("auth/yo", v.YoVista.as_view()),
    path("auth/google", v.GoogleVista.as_view()),
    path("auth/google/callback", v.GoogleCallbackVista.as_view()),
    path("auth/recuperar", v.RecuperarVista.as_view()),
    path("auth/restablecer", v.RestablecerVista.as_view()),
    path("auth/cambiar-contrasena", v.CambiarContrasenaVista.as_view()),
    path("mfa/activar", v.MfaActivarVista.as_view()),
    path("mfa/confirmar", v.MfaConfirmarVista.as_view()),
    path("mfa/estado", v.MfaEstadoVista.as_view()),
    path("mfa/desactivar", v.MfaDesactivarVista.as_view()),
]
