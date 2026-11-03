"""Mensajes propios, y conversaciones y chat del panel (solo staff)."""

from typing import Any

from rest_framework import serializers
from rest_framework.permissions import IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response

from masssend.application.envio.consultas import (
    ConversacionVista,
    Direccion,
    FiltroMensajes,
    MensajeVista,
)
from masssend.domain.envio.entrega import EstadoEntrega
from masssend.domain.shared.errores import DatosInvalidos
from masssend.domain.shared.identificadores import id_publico
from masssend.infrastructure.composition.envio import contenedor_envio as envio
from masssend.interfaces.http.contactos.vistas import EliminarLote, validar
from masssend.interfaces.http.shared.paginacion import peticion_pagina, respuesta_pagina
from masssend.interfaces.http.shared.vistas import VistaApi, cuenta_actual


class TextoChat(serializers.Serializer):
    texto = serializers.CharField(max_length=4096, trim_whitespace=False)


def mensaje_json(mensaje: MensajeVista) -> dict[str, Any]:
    return {
        "id": str(mensaje.id),
        "telefono": mensaje.telefono,
        "nombre": mensaje.nombre,
        "texto": mensaje.texto,
        "direccion": mensaje.direccion.value,
        "estado": mensaje.estado.value,
        "fecha": mensaje.fecha.isoformat(),
        "campana_id": str(mensaje.campana_id) if mensaje.campana_id else None,
        "campana": mensaje.campana,
    }


def conversacion_json(conversacion: ConversacionVista) -> dict[str, Any]:
    return {
        "telefono": conversacion.telefono,
        "nombre": conversacion.nombre,
        "ultimo_texto": conversacion.ultimo_texto,
        "ultima_direccion": conversacion.ultima_direccion.value,
        "ultima_fecha": conversacion.ultima_fecha.isoformat(),
        "mensajes": conversacion.mensajes,
    }


def _opcion(request: Request, clave: str, tipo: Any) -> Any:
    valor = request.query_params.get(clave)
    if not valor:
        return None
    try:
        return tipo(valor)
    except ValueError as error:
        opciones = ", ".join(e.value for e in tipo)
        raise DatosInvalidos(f"Valor desconocido. Usa {opciones}.", clave) from error


class MensajesVista(VistaApi):
    def get(self, request: Request) -> Response:
        filtro = FiltroMensajes(
            texto=request.query_params.get("texto") or None,
            direccion=_opcion(request, "direccion", Direccion),
            estado=_opcion(request, "estado", EstadoEntrega),
            telefono=request.query_params.get("telefono") or None,
        )
        pagina = envio.listar_mensajes().ejecutar(
            cuenta_actual(request), filtro, peticion_pagina(request)
        )
        return respuesta_pagina(pagina, mensaje_json)


class EliminarMensajesVista(VistaApi):
    def post(self, request: Request) -> Response:
        datos = validar(EliminarLote, request.data)
        ids = [id_publico(valor, "ids") for valor in datos["ids"]]
        eliminados = envio.eliminar_mensajes().ejecutar(cuenta_actual(request), ids)
        return Response({"eliminados": eliminados})


class VistaStaff(VistaApi):
    permission_classes = [IsAdminUser]


class ConversacionesVista(VistaStaff):
    def get(self, request: Request) -> Response:
        cuenta_actual(request)
        pagina = envio.listar_conversaciones().ejecutar(peticion_pagina(request))
        return respuesta_pagina(pagina, conversacion_json)


class ConversacionMensajesVista(VistaStaff):
    """Envia un mensaje suelto desde el chat del panel. No usa creditos."""

    def post(self, request: Request, telefono: str) -> Response:
        texto = validar(TextoChat, request.data)["texto"]
        mensaje = envio.enviar_mensaje_chat().ejecutar(cuenta_actual(request), telefono, texto)
        return Response(
            {
                "id": str(mensaje.id),
                "telefono": mensaje.telefono,
                "estado": mensaje.estado.value,
                "detalle": mensaje.detalle,
            },
            status=201,
        )
