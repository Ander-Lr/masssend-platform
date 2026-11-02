"""Manejador unico de errores: todo fallo de la v1 sale como RFC 9457."""

import logging
import math
from typing import Any

from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpRequest, JsonResponse
from rest_framework import exceptions as drf
from rest_framework.views import set_rollback

from masssend.domain.shared import errores as dominio

logger = logging.getLogger(__name__)

TIPO_CONTENIDO = "application/problem+json"

ERRORES_DOMINIO: dict[type[dominio.ErrorDominio], tuple[int, str]] = {
    dominio.DatosInvalidos: (422, "Datos inválidos"),
    dominio.NoAutenticado: (401, "No autenticado"),
    dominio.SinPermiso: (403, "Sin permiso"),
    dominio.RecursoNoEncontrado: (404, "Recurso no encontrado"),
    dominio.EstadoInvalido: (409, "Estado inválido"),
    dominio.SaldoInsuficiente: (402, "Saldo insuficiente"),
    dominio.DemasiadosIntentos: (429, "Demasiados intentos"),
    dominio.ServicioNoDisponible: (503, "Servicio no disponible"),
}

ERRORES_DRF: tuple[tuple[type[Exception], int, str, str], ...] = (
    (drf.NotAuthenticated, 401, "no_autenticado", "No autenticado"),
    (drf.AuthenticationFailed, 401, "no_autenticado", "No autenticado"),
    (drf.PermissionDenied, 403, "sin_permiso", "Sin permiso"),
    (PermissionDenied, 403, "sin_permiso", "Sin permiso"),
    (drf.NotFound, 404, "recurso_no_encontrado", "Recurso no encontrado"),
    (Http404, 404, "recurso_no_encontrado", "Recurso no encontrado"),
    (drf.MethodNotAllowed, 405, "metodo_no_permitido", "Método no permitido"),
    (drf.NotAcceptable, 406, "formato_no_aceptable", "Formato no aceptable"),
    (drf.UnsupportedMediaType, 415, "formato_no_soportado", "Formato no soportado"),
    (drf.ParseError, 400, "peticion_invalida", "Petición inválida"),
)


def problema(
    instancia: str,
    estado: int,
    codigo: str,
    titulo: str,
    detalle: str,
    **extensiones: Any,
) -> JsonResponse:
    cuerpo = {
        "type": f"urn:masssend:problema:{codigo}",
        "title": titulo,
        "status": estado,
        "detail": detalle,
        "instance": instancia,
        "codigo": codigo,
        **extensiones,
    }
    return JsonResponse(
        cuerpo,
        status=estado,
        content_type=TIPO_CONTENIDO,
        json_dumps_params={"ensure_ascii": False},
    )


def ruta_no_encontrada(request: HttpRequest, resto: str = "") -> JsonResponse:
    return problema(
        request.path,
        404,
        "recurso_no_encontrado",
        "Recurso no encontrado",
        "La ruta solicitada no existe.",
    )


def manejar_excepcion(exc: Exception, contexto: dict[str, Any]) -> JsonResponse:
    set_rollback()
    instancia = contexto["request"].path
    if isinstance(exc, dominio.ErrorDominio):
        return _desde_dominio(exc, instancia)
    if isinstance(exc, drf.ValidationError):
        return problema(
            instancia,
            422,
            dominio.DatosInvalidos.codigo,
            "Datos inválidos",
            "La petición contiene datos inválidos.",
            errores=_aplanar(exc.detail),
        )
    if isinstance(exc, drf.Throttled):
        return _limite_superado(exc, instancia)
    for clase, estado, codigo, titulo in ERRORES_DRF:
        if isinstance(exc, clase):
            respuesta = problema(instancia, estado, codigo, titulo, _detalle(exc, titulo))
            encabezado = getattr(exc, "auth_header", None)
            if encabezado:
                respuesta["WWW-Authenticate"] = encabezado
            return respuesta
    logger.exception("Error no controlado en la API v1.", exc_info=exc)
    return problema(
        instancia,
        500,
        "error_interno",
        "Error interno",
        "Ocurrió un error inesperado.",
    )


def _desde_dominio(exc: dominio.ErrorDominio, instancia: str) -> JsonResponse:
    estado, titulo = next(
        (valor for clase, valor in ERRORES_DOMINIO.items() if isinstance(exc, clase)),
        (500, "Error interno"),
    )
    if isinstance(exc, dominio.DatosInvalidos):
        return problema(instancia, estado, exc.codigo, titulo, exc.mensaje, campo=exc.campo)
    if isinstance(exc, dominio.SaldoInsuficiente):
        return problema(
            instancia,
            estado,
            exc.codigo,
            titulo,
            exc.mensaje,
            requerido=exc.requerido,
            disponible=exc.disponible,
        )
    if isinstance(exc, dominio.DemasiadosIntentos):
        respuesta = problema(
            instancia,
            estado,
            exc.codigo,
            titulo,
            exc.mensaje,
            espera_segundos=exc.espera_segundos,
        )
        respuesta["Retry-After"] = str(exc.espera_segundos)
        return respuesta
    return problema(instancia, estado, exc.codigo, titulo, exc.mensaje)


def _limite_superado(exc: drf.Throttled, instancia: str) -> JsonResponse:
    espera = math.ceil(exc.wait or 1)
    respuesta = problema(
        instancia,
        429,
        dominio.DemasiadosIntentos.codigo,
        "Demasiados intentos",
        "Se superó el límite de peticiones.",
        espera_segundos=espera,
    )
    respuesta["Retry-After"] = str(espera)
    return respuesta


def _detalle(exc: Exception, por_defecto: str) -> str:
    detalle = getattr(exc, "detail", None)
    return detalle if isinstance(detalle, str) else por_defecto


def _aplanar(detalle: Any, campo: str = "") -> list[dict[str, str]]:
    if isinstance(detalle, dict):
        return [
            error
            for clave, valor in detalle.items()
            for error in _aplanar(valor, f"{campo}.{clave}" if campo else str(clave))
        ]
    if isinstance(detalle, list):
        return [error for valor in detalle for error in _aplanar(valor, campo)]
    return [{"campo": campo, "detalle": str(detalle)}]
