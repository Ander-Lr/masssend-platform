from dataclasses import asdict
from typing import Any

from rest_framework import serializers
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response

from masssend.application.identidad.puertos import TareaCorreo
from masssend.domain.identidad.notificacion import Adjunto, Notificacion
from masssend.infrastructure.composition.identidad import contenedor_identidad as identidad
from masssend.interfaces.http.shared.paginacion import peticion_pagina, respuesta_pagina
from masssend.interfaces.http.shared.vistas import VistaApi, cuenta_actual


class Entrada(serializers.Serializer):
    destinatario = serializers.CharField(max_length=254)
    asunto = serializers.CharField(max_length=500, trim_whitespace=False)
    titulo = serializers.CharField(max_length=500)
    mensaje = serializers.CharField(max_length=10000)
    firma = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    archivo = serializers.FileField(required=False)


class VistaStaff(VistaApi):
    permission_classes = [IsAdminUser]


def tarea_json(tarea: TareaCorreo) -> dict[str, Any]:
    datos = asdict(tarea)
    datos["creada_en"] = tarea.creada_en.isoformat()
    return datos


class NotificacionesVista(VistaStaff):
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def post(self, request: Request) -> Response:
        cuenta_actual(request)
        entrada = Entrada(data=request.data)
        entrada.is_valid(raise_exception=True)
        datos: dict[str, Any] = dict(entrada.validated_data)
        archivo = datos.get("archivo")
        adjunto = (
            Adjunto.crear(
                archivo.name,
                archivo.content_type,
                archivo.read(),
                identidad.maximo_adjunto_mb(),
            )
            if archivo
            else None
        )
        notificacion = Notificacion.crear(
            datos["destinatario"],
            datos["asunto"],
            datos["titulo"],
            datos["mensaje"],
            datos["firma"],
            adjunto,
        )
        tarea_id = identidad.enviar_notificacion().ejecutar(notificacion)
        return Response(
            {"tarea_id": str(tarea_id), "destinatario": notificacion.destinatario}, status=202
        )


class TareasVista(VistaStaff):
    def get(self, request: Request) -> Response:
        cuenta_actual(request)
        pagina, pausada = identidad.consultar_cola().ejecutar(peticion_pagina(request))
        respuesta = respuesta_pagina(pagina, tarea_json)
        respuesta.data["pausada"] = pausada
        return respuesta


class PausarVista(VistaStaff):
    def post(self, request: Request) -> Response:
        cuenta_actual(request)
        identidad.controlar_cola().pausar()
        return Response({"pausada": True})


class ReanudarVista(VistaStaff):
    def post(self, request: Request) -> Response:
        cuenta_actual(request)
        identidad.controlar_cola().reanudar()
        return Response({"pausada": False})
