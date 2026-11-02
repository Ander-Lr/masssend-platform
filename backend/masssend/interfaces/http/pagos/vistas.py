from typing import Any

from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response

from masssend.domain.shared.identificadores import id_publico
from masssend.infrastructure.composition.creditos import contenedor_creditos as creditos
from masssend.interfaces.http.shared.vistas import VistaApi, cuenta_actual


class Checkout(serializers.Serializer):
    """Sin monto: un campo extra del cliente se ignora, el precio lo fija el servidor."""

    paquete_id = serializers.IntegerField(min_value=1)
    pasarela = serializers.CharField(max_length=20)


class Confirmar(serializers.Serializer):
    compra_id = serializers.CharField(max_length=36)
    datos_pasarela = serializers.DictField(required=False, default=dict)


def validar(clase: type[serializers.Serializer], datos: Any) -> dict[str, Any]:
    entrada = clase(data=datos)
    entrada.is_valid(raise_exception=True)
    return dict(entrada.validated_data)


class CheckoutVista(VistaApi):
    def post(self, request: Request) -> Response:
        datos = validar(Checkout, request.data)
        compra = creditos.iniciar_compra().ejecutar(
            cuenta_actual(request), datos["paquete_id"], datos["pasarela"]
        )
        return Response(
            {
                "compra_id": str(compra.compra_id),
                "pasarela": compra.pasarela,
                "referencia": compra.referencia,
                "url_pago": compra.url_pago,
                "monto": f"{compra.monto.como_decimal():.2f}",
                "moneda": compra.monto.moneda,
                "creditos": compra.creditos,
            },
            status=201,
        )


class ConfirmarVista(VistaApi):
    def post(self, request: Request) -> Response:
        datos = validar(Confirmar, request.data)
        resultado = creditos.confirmar_compra().ejecutar(
            cuenta_actual(request),
            id_publico(datos["compra_id"], "compra_id"),
            datos["datos_pasarela"],
        )
        return Response(
            {
                "estado": resultado.estado,
                "creditos": resultado.creditos,
                "ya_procesada": resultado.ya_procesada,
            }
        )
