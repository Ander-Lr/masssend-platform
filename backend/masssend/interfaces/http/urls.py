"""Rutas de /api/v1/. Cada modulo agrega aqui una sola linea de include."""

from django.urls import include, path, re_path

from masssend.interfaces.http.shared.problemas import ruta_no_encontrada
from masssend.interfaces.http.shared.salud import SaludVista

urlpatterns = [
    path("salud", SaludVista.as_view(), name="v1_salud"),
    path("", include("masssend.interfaces.http.identidad.urls")),
    path("", include("masssend.interfaces.http.creditos.urls")),
    path("", include("masssend.interfaces.http.pagos.urls")),
    path("", include("masssend.interfaces.http.ia.urls")),
    path("", include("masssend.interfaces.http.notificaciones.urls")),
    path("", include("masssend.interfaces.http.contactos.urls")),
    # Debe ser siempre la ultima: una ruta desconocida responde problem+json.
    re_path(r"^(?P<resto>.*)$", ruta_no_encontrada, name="v1_no_encontrada"),
]
