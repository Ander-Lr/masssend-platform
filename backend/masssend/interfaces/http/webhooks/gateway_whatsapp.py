"""Webhooks del gateway de WhatsApp: /api/v1/webhooks/whatsapp/...

No usan JWT: se autentican con la firma HMAC de cada aviso. Una firma
invalida responde 401 en problem+json. Repetir un aviso no cambia nada.
"""

from typing import Any

from django.conf import settings
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from masssend.application.envio.webhooks import MensajeEntrante, ResultadoGateway
from masssend.domain.envio.entrega import EstadoEntrega
from masssend.domain.shared.errores import NoAutenticado
from masssend.domain.shared.identificadores import id_publico
from masssend.infrastructure.composition.envio import contenedor_envio as envio
from masssend.infrastructure.composition.root import contenedor
from masssend.interfaces.http.contactos.vistas import validar
from masssend.interfaces.http.shared.vistas import VistaApi
from masssend.interfaces.http.webhooks import firma

ACUSES = [EstadoEntrega.ENVIADO, EstadoEntrega.ENTREGADO, EstadoEntrega.LEIDO]


class Entrante(serializers.Serializer):
    id = serializers.CharField(max_length=200, required=False, allow_null=True, default=None)
    telefono = serializers.CharField(max_length=50)
    texto = serializers.CharField(max_length=4096, trim_whitespace=False)


class Acuse(serializers.Serializer):
    id_externo = serializers.CharField(max_length=200)
    estado = serializers.ChoiceField(choices=[e.value for e in ACUSES])


class Resultado(serializers.Serializer):
    envio_id = serializers.CharField(max_length=36, required=False, allow_null=True, default=None)
    telefono = serializers.CharField(max_length=50)
    estado = serializers.ChoiceField(choices=["enviado", "fallido"])
    id_externo = serializers.CharField(
        max_length=200, required=False, allow_null=True, allow_blank=True, default=None
    )
    error = serializers.CharField(
        max_length=2000, required=False, allow_null=True, allow_blank=True, default=None
    )


class VistaWebhook(VistaApi):
    authentication_classes: list[Any] = []
    permission_classes = [AllowAny]
    throttle_classes: list[Any] = []

    def initial(self, request: Request, *args: Any, **kwargs: Any) -> None:
        super().initial(request, *args, **kwargs)
        try:
            firma.verificar(
                request.body,
                request.headers.get(firma.CABECERA_TIEMPO),
                request.headers.get(firma.CABECERA_FIRMA),
                settings.WHATSAPP_WEBHOOK_TOKEN,
                contenedor.reloj().ahora().timestamp(),
            )
        except firma.FirmaInvalida as error:
            raise NoAutenticado(str(error)) from error


class MensajesVista(VistaWebhook):
    """Mensaje recibido. Si dice BAJA, el numero se da de baja en todas las libretas."""

    def post(self, request: Request) -> Response:
        datos = validar(Entrante, request.data)
        registrado = envio.recibir_mensaje().ejecutar(
            MensajeEntrante(datos["telefono"], datos["texto"], datos["id"])
        )
        return Response(
            {
                "repetido": registrado.repetido,
                "baja": registrado.baja,
                "contactos_dados_de_baja": registrado.contactos_dados_de_baja,
            }
        )


class AcusesVista(VistaWebhook):
    """Entregado o leido. El estado solo avanza."""

    def post(self, request: Request) -> Response:
        datos = validar(Acuse, request.data)
        actualizados = envio.registrar_acuse().ejecutar(
            datos["id_externo"], EstadoEntrega(datos["estado"])
        )
        return Response({"actualizados": actualizados})


class ResultadosVista(VistaWebhook):
    """Resultado de un envio. Llega con el envio_id que se mando al gateway."""

    def post(self, request: Request) -> Response:
        datos = validar(Resultado, request.data)
        envio_id = id_publico(datos["envio_id"], "envio_id") if datos["envio_id"] else None
        actualizados = envio.registrar_resultado().ejecutar(
            ResultadoGateway(
                envio_id,
                datos["telefono"],
                datos["estado"] == "enviado",
                datos["id_externo"] or None,
                datos["error"] or None,
            )
        )
        return Response({"actualizados": actualizados})
