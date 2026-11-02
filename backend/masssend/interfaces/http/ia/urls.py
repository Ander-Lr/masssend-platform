from django.urls import path

from masssend.interfaces.http.ia import vistas as v

urlpatterns = [
    path("asistente/mensajes", v.MensajesVista.as_view()),
    path("asistente/salud", v.SaludVista.as_view()),
]
