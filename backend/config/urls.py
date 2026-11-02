"""Rutas de la API v1 junto a las rutas del sistema actual."""

from django.urls import include, path

from core.urls import urlpatterns as rutas_actuales

urlpatterns = [
    path("api/v1/", include("masssend.interfaces.http.urls")),
    *rutas_actuales,
]
