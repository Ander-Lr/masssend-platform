from django.urls import path

from masssend.interfaces.http.webhooks import gateway_whatsapp as v

urlpatterns = [
    path("webhooks/whatsapp/mensajes", v.MensajesVista.as_view()),
    path("webhooks/whatsapp/acuses", v.AcusesVista.as_view()),
    path("webhooks/whatsapp/resultados", v.ResultadosVista.as_view()),
]
