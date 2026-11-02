from django.urls import path

from masssend.interfaces.http.pagos import vistas as v

urlpatterns = [
    path("pagos/checkout", v.CheckoutVista.as_view()),
    path("pagos/confirmar", v.ConfirmarVista.as_view()),
]
