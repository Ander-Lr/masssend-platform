from dataclasses import asdict
from typing import Any

from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response

from masssend.domain.ia.consulta import Turno
from masssend.infrastructure.composition.ia import contenedor_ia as ia
from masssend.interfaces.http.shared.limites import LimiteAsistente
from masssend.interfaces.http.shared.vistas import VistaApi, cuenta_actual


class TurnoEntrada(serializers.Serializer):
    rol = serializers.ChoiceField(choices=["user", "assistant"])
    contenido = serializers.CharField(max_length=5000)


class Mensaje(serializers.Serializer):
    pregunta = serializers.CharField(max_length=5000, allow_blank=True)
    historial = TurnoEntrada(many=True, required=False, default=list)


class MensajesVista(VistaApi):
    throttle_classes = [LimiteAsistente]

    def post(self, request: Request) -> Response:
        owner_id = cuenta_actual(request)
        entrada = Mensaje(data=request.data)
        entrada.is_valid(raise_exception=True)
        datos: dict[str, Any] = dict(entrada.validated_data)
        historial = [Turno(t["rol"], t["contenido"]) for t in datos["historial"]]
        return Response(asdict(ia.consultar().ejecutar(owner_id, datos["pregunta"], historial)))


class SaludVista(VistaApi):
    def get(self, request: Request) -> Response:
        cuenta_actual(request)
        return Response(asdict(ia.revisar().ejecutar()))
