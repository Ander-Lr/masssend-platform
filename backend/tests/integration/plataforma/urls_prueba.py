"""Rutas solo para pruebas: ejercitan la plataforma antes de que existan modulos."""

from typing import Any

from django.urls import include, path
from rest_framework import serializers
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response

from masssend.domain.shared import errores
from masssend.domain.shared.paginacion import Cursor, Pagina
from masssend.interfaces.http.shared.limites import LimiteAnonimo
from masssend.interfaces.http.shared.paginacion import peticion_pagina, respuesta_pagina
from masssend.interfaces.http.shared.vistas import VistaApi

ERRORES: dict[str, errores.ErrorDominio] = {
    "datos": errores.DatosInvalidos("Nombre vacío.", "nombre"),
    "sesion": errores.NoAutenticado("Sin sesión."),
    "permiso": errores.SinPermiso("Solo staff."),
    "ajeno": errores.RecursoNoEncontrado("No existe."),
    "estado": errores.EstadoInvalido("Ya terminó."),
    "saldo": errores.SaldoInsuficiente("Sin saldo.", requerido=5, disponible=2),
    "intentos": errores.DemasiadosIntentos("Espera.", 30),
    "servicio": errores.ServicioNoDisponible("WhatsApp desconectado."),
}


class Publica(VistaApi):
    permission_classes = [AllowAny]
    throttle_classes: list[Any] = []


class ErrorVista(Publica):
    def get(self, request: Request, nombre: str) -> Response:
        raise ERRORES[nombre]


class FalloVista(Publica):
    def get(self, request: Request) -> Response:
        raise RuntimeError("password=secreto-interno")


class Entrada(serializers.Serializer):
    nombre = serializers.CharField()
    edad = serializers.IntegerField()


class ValidarVista(Publica):
    def post(self, request: Request) -> Response:
        entrada = Entrada(data=request.data)
        entrada.is_valid(raise_exception=True)
        return Response(entrada.validated_data, status=201)


class PerfilVista(VistaApi):
    throttle_classes: list[Any] = []

    def get(self, request: Request) -> Response:
        return Response({"usuario": request.user.get_username()})


class StaffVista(VistaApi):
    permission_classes = [IsAdminUser]
    throttle_classes: list[Any] = []

    def get(self, request: Request) -> Response:
        return Response({"ok": True})


class LimitadaVista(VistaApi):
    permission_classes = [AllowAny]
    throttle_classes = [LimiteAnonimo]

    def get(self, request: Request) -> Response:
        return Response({"ok": True})


class ListaVista(Publica):
    def get(self, request: Request) -> Response:
        peticion = peticion_pagina(request)
        inicio = int(peticion.cursor.valores[0]) if peticion.cursor else 0
        filas = list(range(inicio + 1, 6))[: peticion.limite + 1]
        pagina = Pagina.desde_filas(filas, peticion, lambda fila: Cursor((str(fila),)))
        return respuesta_pagina(pagina, lambda fila: {"id": fila})


urlpatterns = [
    path("api/v1/prueba/error/<str:nombre>", ErrorVista.as_view()),
    path("api/v1/prueba/fallo", FalloVista.as_view()),
    path("api/v1/prueba/validar", ValidarVista.as_view()),
    path("api/v1/prueba/perfil", PerfilVista.as_view()),
    path("api/v1/prueba/staff", StaffVista.as_view()),
    path("api/v1/prueba/limitada", LimitadaVista.as_view()),
    path("api/v1/prueba/lista", ListaVista.as_view()),
    path("", include("config.urls")),
]
