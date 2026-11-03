from django.urls import path

from masssend.interfaces.http.reportes import vistas as v

urlpatterns = [
    path("reportes", v.ReportesVista.as_view()),
]
