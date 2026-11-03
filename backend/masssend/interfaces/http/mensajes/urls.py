from django.urls import path

from masssend.interfaces.http.mensajes import vistas as v

urlpatterns = [
    path("mensajes", v.MensajesVista.as_view()),
    path("mensajes/eliminar-lote", v.EliminarMensajesVista.as_view()),
    path("conversaciones", v.ConversacionesVista.as_view()),
    path("conversaciones/<str:telefono>/mensajes", v.ConversacionMensajesVista.as_view()),
]
