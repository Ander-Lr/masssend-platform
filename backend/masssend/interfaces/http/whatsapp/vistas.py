"""Conexion del numero de WhatsApp. Solo staff: es el numero de toda la plataforma."""

from rest_framework import serializers
from rest_framework.permissions import IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response

from masssend.infrastructure.composition.envio import contenedor_envio as envio
from masssend.interfaces.http.contactos.vistas import validar
from masssend.interfaces.http.shared.vistas import VistaApi, cuenta_actual


class Vinculacion(serializers.Serializer):
    telefono = serializers.CharField(max_length=50)


class VistaStaff(VistaApi):
    permission_classes = [IsAdminUser]


class EstadoVista(VistaStaff):
    def get(self, request: Request) -> Response:
        cuenta_actual(request)
        estado = envio.consultar_whatsapp().ejecutar()
        return Response(
            {"conectado": estado.conectado, "codigo_vinculacion": estado.codigo_vinculacion}
        )


class VinculacionVista(VistaStaff):
    def post(self, request: Request) -> Response:
        cuenta_actual(request)
        telefono = validar(Vinculacion, request.data)["telefono"]
        codigo = envio.vincular_whatsapp().ejecutar(telefono)
        return Response(
            {
                "codigo": codigo,
                "detalle": "Escribe el código en WhatsApp > Dispositivos vinculados."
                if codigo
                else "El código se está generando; consulta el estado en unos segundos.",
            }
        )


class CerrarSesionVista(VistaStaff):
    def post(self, request: Request) -> Response:
        cuenta_actual(request)
        envio.cerrar_sesion_whatsapp().ejecutar()
        return Response({"detalle": "WhatsApp se está desconectando."})
