"""Vistas delgadas de /campanas: validan el formato, llaman al caso de uso y responden."""

from typing import Any

from django.http import HttpResponse
from rest_framework import serializers
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response

from masssend.application.campanas.campanas import CambiosCampana, DetalleCampana
from masssend.domain.campanas.archivo import LIMITE_MB
from masssend.domain.campanas.campana import MAX_MENSAJE, MAX_NOMBRE, Campana, EstadoCampana
from masssend.domain.campanas.repositorios import FiltroCampanas
from masssend.domain.shared.errores import DatosInvalidos, RecursoNoEncontrado
from masssend.domain.shared.identificadores import IdPublico, id_publico
from masssend.infrastructure.composition.campanas import contenedor_campanas as campanas
from masssend.interfaces.http.contactos.vistas import Etiquetas, validar
from masssend.interfaces.http.shared.paginacion import peticion_pagina, respuesta_pagina
from masssend.interfaces.http.shared.vistas import VistaApi, cuenta_actual

MAXIMO_SUBIDA = max(LIMITE_MB.values()) * 1024 * 1024


class Crear(serializers.Serializer):
    nombre = serializers.CharField(max_length=MAX_NOMBRE, allow_blank=True)
    mensaje = serializers.CharField(max_length=MAX_MENSAJE, allow_blank=True, trim_whitespace=False)
    etiquetas = Etiquetas(required=False, default="")


class Editar(serializers.Serializer):
    nombre = serializers.CharField(max_length=MAX_NOMBRE, required=False, allow_blank=True)
    mensaje = serializers.CharField(
        max_length=MAX_MENSAJE, required=False, allow_blank=True, trim_whitespace=False
    )
    etiquetas = Etiquetas(required=False)


class Subir(serializers.Serializer):
    archivo = serializers.FileField(allow_empty_file=True)


def id_de_ruta(valor: str) -> IdPublico:
    """Un id mal formado en la ruta se trata como inexistente."""
    try:
        return id_publico(valor)
    except DatosInvalidos as error:
        raise RecursoNoEncontrado("La campaña no existe.") from error


def campana_json(campana: Campana, destinatarios: int | None = None) -> dict[str, Any]:
    datos: dict[str, Any] = {
        "id": str(campana.id),
        "nombre": campana.nombre,
        "mensaje": campana.mensaje,
        "etiquetas": list(campana.etiquetas),
        "estado": campana.estado.value,
        "tiene_adjunto": campana.adjunto is not None,
        "adjunto_url": f"/api/v1/campanas/{campana.id}/adjunto" if campana.adjunto else None,
    }
    if destinatarios is not None:
        datos["destinatarios"] = destinatarios
    return datos


def detalle_json(detalle: DetalleCampana) -> dict[str, Any]:
    return campana_json(detalle.campana, detalle.destinatarios)


def filtro_estado(request: Request) -> FiltroCampanas:
    valor = request.query_params.get("estado")
    if not valor:
        return FiltroCampanas()
    try:
        return FiltroCampanas(EstadoCampana(valor))
    except ValueError as error:
        opciones = ", ".join(e.value for e in EstadoCampana)
        raise DatosInvalidos(f"Estado desconocido. Usa {opciones}.", "estado") from error


class CampanasVista(VistaApi):
    def get(self, request: Request) -> Response:
        pagina = campanas.listar_campanas().ejecutar(
            cuenta_actual(request), filtro_estado(request), peticion_pagina(request)
        )
        return respuesta_pagina(pagina, campana_json)

    def post(self, request: Request) -> Response:
        datos = validar(Crear, request.data)
        detalle = campanas.crear_campana().ejecutar(
            cuenta_actual(request), datos["nombre"], datos["mensaje"], datos["etiquetas"]
        )
        return Response(detalle_json(detalle), status=201)


class CampanaVista(VistaApi):
    def get(self, request: Request, campana_id: str) -> Response:
        detalle = campanas.obtener_campana().ejecutar(
            cuenta_actual(request), id_de_ruta(campana_id)
        )
        return Response(detalle_json(detalle))

    def patch(self, request: Request, campana_id: str) -> Response:
        datos = validar(Editar, request.data)
        detalle = campanas.editar_campana().ejecutar(
            cuenta_actual(request), id_de_ruta(campana_id), CambiosCampana(**datos)
        )
        return Response(detalle_json(detalle))

    def delete(self, request: Request, campana_id: str) -> Response:
        campanas.eliminar_campana().ejecutar(cuenta_actual(request), id_de_ruta(campana_id))
        return Response(status=204)


class AdjuntoVista(VistaApi):
    """El archivo nunca se expone por URL directa: solo el dueno lo descarga aqui."""

    parser_classes = [MultiPartParser, FormParser]

    def post(self, request: Request, campana_id: str) -> Response:
        owner_id = cuenta_actual(request)
        archivo = validar(Subir, request.data)["archivo"]
        if archivo.size > MAXIMO_SUBIDA:
            raise DatosInvalidos(
                f"El archivo supera el límite de {max(LIMITE_MB.values())} MB.", "archivo"
            )
        detalle = campanas.subir_adjunto().ejecutar(
            owner_id, id_de_ruta(campana_id), archivo.name, archivo.read()
        )
        return Response(detalle_json(detalle))

    def get(self, request: Request, campana_id: str) -> HttpResponse:
        archivo = campanas.descargar_adjunto().ejecutar(
            cuenta_actual(request), id_de_ruta(campana_id)
        )
        respuesta = HttpResponse(archivo.contenido, content_type=archivo.tipo)
        respuesta["Content-Disposition"] = f'inline; filename="{archivo.nombre}"'
        respuesta["X-Content-Type-Options"] = "nosniff"
        respuesta["Cache-Control"] = "private, no-store"
        return respuesta
