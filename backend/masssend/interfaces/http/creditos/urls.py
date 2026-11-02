from django.urls import path

from masssend.interfaces.http.creditos import vistas as v

urlpatterns = [
    path("creditos/paquetes", v.PaquetesVista.as_view()),
    path("creditos/saldo", v.SaldoVista.as_view()),
    path("creditos/movimientos", v.MovimientosVista.as_view()),
]
