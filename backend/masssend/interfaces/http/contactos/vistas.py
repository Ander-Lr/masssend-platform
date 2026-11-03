"""Vistas delgadas de /contactos: validan el formato, llaman al caso de uso y responden."""

from typing import Any

from rest_framework import serializers
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response

from masssend.application.campanas.contactos import CambiosContacto
from masssend.application.campanas.importacion import ResultadoImportacion
from masssend.domain.campanas.contacto import Contacto
from masssend.domain.campanas.repositorios import FiltroContactos
from masssend.domain.shared.errores import DatosInvalidos, RecursoNoEncontrado
from masssend.domain.shared.identificadores import IdPublico, id_publico
from masssend.infrastructure.composition.campanas import contenedor_campanas as campanas
from masssend.interfaces.http.contactos.csv_contactos import LectorCsv
from masssend.interfaces.http.shared.paginacion import peticion_pagina, respuesta_pagina
from masssend.interfaces.http.shared.vistas import VistaApi, cuenta_actual

MAXIMO_CSV_MB = 5
MAXIMO_RECHAZADAS = 100
EXTENSIONES_CSV = (".csv", ".txt")


class Etiquetas(serializers.Field):
    """Acepta ["vip", "cliente"] o "vip, cliente"."""

    def to_internal_value(self, dato: Any) -> str | list[str]:
        if isinstance(dato, str):
            return dato
        if isinstance(dato, list) and all(isinstance(e, str) for e in dato):
            return dato
        raise serializers.ValidationError("Debe ser una lista de textos o un texto.")


class Crear(serializers.Serializer):
    telefono = serializers.CharField(max_length=50)
    nombre = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    etiquetas = Etiquetas(required=False, default="")


class Editar(serializers.Serializer):
    nombre = serializers.CharField(max_length=150, required=False, allow_blank=True)
    etiquetas = Etiquetas(required=False)
    datos = serializers.DictField(
        child=serializers.CharField(max_length=500, allow_blank=True), required=False
    )
    dado_de_baja = serializers.BooleanField(required=False)


class EliminarLote(serializers.Serializer):
    ids = serializers.ListField(child=serializers.CharField(max_length=36), allow_empty=True)


class Importar(serializers.Serializer):
    archivo = serializers.FileField()
    separador = serializers.CharField(max_length=3, required=False, default=",")
    encabezado = serializers.BooleanField(required=False, default=True)


def validar(clase: type[serializers.Serializer], datos: Any) -> dict[str, Any]:
    entrada = clase(data=datos)
    entrada.is_valid(raise_exception=True)
    return dict(entrada.validated_data)


def id_de_ruta(valor: str) -> IdPublico:
    """Un id mal formado en la ruta se trata como inexistente."""
    try:
        return id_publico(valor)
    except DatosInvalidos as error:
        raise RecursoNoEncontrado("El contacto no existe.") from error


def contacto_json(contacto: Contacto) -> dict[str, Any]:
    return {
        "id": str(contacto.id),
        "telefono": contacto.telefono.numero,
        "nombre": contacto.nombre,
        "etiquetas": list(contacto.etiquetas),
        "datos": dict(contacto.datos),
        "dado_de_baja": contacto.dado_de_baja,
    }


def importacion_json(resultado: ResultadoImportacion) -> dict[str, Any]:
    return {
        "total": resultado.total,
        "creados": resultado.creados,
        "actualizados": resultado.actualizados,
        "total_rechazadas": len(resultado.rechazadas),
        "rechazadas": [
            {"fila": r.numero, "telefono": r.telefono, "campo": r.campo, "mensaje": r.mensaje}
            for r in resultado.rechazadas[:MAXIMO_RECHAZADAS]
        ],
    }


class ContactosVista(VistaApi):
    def get(self, request: Request) -> Response:
        filtro = FiltroContactos(
            texto=request.query_params.get("texto") or None,
            etiqueta=request.query_params.get("etiqueta") or None,
        )
        pagina = campanas.listar_contactos().ejecutar(
            cuenta_actual(request), filtro, peticion_pagina(request)
        )
        return respuesta_pagina(pagina, contacto_json)

    def post(self, request: Request) -> Response:
        datos = validar(Crear, request.data)
        guardado = campanas.guardar_contacto().ejecutar(
            cuenta_actual(request), datos["telefono"], datos["nombre"], datos["etiquetas"]
        )
        return Response(contacto_json(guardado.contacto), status=201 if guardado.creado else 200)


class ContactoVista(VistaApi):
    def get(self, request: Request, contacto_id: str) -> Response:
        contacto = campanas.obtener_contacto().ejecutar(
            cuenta_actual(request), id_de_ruta(contacto_id)
        )
        return Response(contacto_json(contacto))

    def patch(self, request: Request, contacto_id: str) -> Response:
        datos = validar(Editar, request.data)
        contacto = campanas.editar_contacto().ejecutar(
            cuenta_actual(request), id_de_ruta(contacto_id), CambiosContacto(**datos)
        )
        return Response(contacto_json(contacto))

    def delete(self, request: Request, contacto_id: str) -> Response:
        campanas.eliminar_contacto().ejecutar(cuenta_actual(request), id_de_ruta(contacto_id))
        return Response(status=204)


class EliminarLoteVista(VistaApi):
    def post(self, request: Request) -> Response:
        datos = validar(EliminarLote, request.data)
        ids = [id_publico(valor, "ids") for valor in datos["ids"]]
        eliminados = campanas.eliminar_contactos().ejecutar(cuenta_actual(request), ids)
        return Response({"eliminados": eliminados})


class EtiquetasVista(VistaApi):
    def get(self, request: Request) -> Response:
        return Response({"datos": campanas.listar_etiquetas().ejecutar(cuenta_actual(request))})


class ImportarVista(VistaApi):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request: Request) -> Response:
        owner_id = cuenta_actual(request)
        datos = validar(Importar, request.data)
        archivo = datos["archivo"]
        if not archivo.name.lower().endswith(EXTENSIONES_CSV):
            raise DatosInvalidos("El archivo debe ser .csv o .txt.", "archivo")
        if archivo.size > MAXIMO_CSV_MB * 1024 * 1024:
            raise DatosInvalidos(f"El archivo supera {MAXIMO_CSV_MB} MB.", "archivo")
        lector = LectorCsv(archivo.file, datos["separador"], datos["encabezado"])
        resultado = campanas.importar_contactos().ejecutar(owner_id, lector.filas())
        return Response(importacion_json(resultado))
