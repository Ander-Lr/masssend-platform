from django.urls import path

from masssend.interfaces.http.notificaciones import vistas as v

urlpatterns = [
    path("notificaciones", v.NotificacionesVista.as_view()),
    path("cola-correos/tareas", v.TareasVista.as_view()),
    path("cola-correos/pausar", v.PausarVista.as_view()),
    path("cola-correos/reanudar", v.ReanudarVista.as_view()),
]
