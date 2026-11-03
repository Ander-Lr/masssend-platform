from django.urls import path

from masssend.interfaces.http.whatsapp import vistas as v

urlpatterns = [
    path("whatsapp/estado", v.EstadoVista.as_view()),
    path("whatsapp/vinculacion", v.VinculacionVista.as_view()),
    path("whatsapp/cerrar-sesion", v.CerrarSesionVista.as_view()),
]
