from django.urls import path

from masssend.interfaces.http.campanas import vistas as v

urlpatterns = [
    path("campanas", v.CampanasVista.as_view()),
    path("campanas/<str:campana_id>", v.CampanaVista.as_view()),
    path("campanas/<str:campana_id>/adjunto", v.AdjuntoVista.as_view()),
]
