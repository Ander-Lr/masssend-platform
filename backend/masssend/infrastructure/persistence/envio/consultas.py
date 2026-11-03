"""Lecturas de mensajes, conversaciones y reportes directo a DTO.

Cada listado usa como maximo tres consultas, sin importar el tamano de la
pagina: el sistema actual hacia una consulta extra por fila para buscar el
nombre del contacto; aqui ese nombre llega en la misma consulta.
"""

from collections.abc import Collection
from datetime import datetime
from typing import Any
from uuid import UUID

from django.db.models import Count, Max, OuterRef, Q, QuerySet, Subquery
from django.db.models.functions import TruncDate

from mass_sender.models import Message
from masssend.application.envio.consultas import (
    ConversacionVista,
    DiaReporte,
    Direccion,
    FiltroMensajes,
    MensajeVista,
    Periodo,
    Reporte,
)
from masssend.domain.envio.entrega import EstadoEntrega
from masssend.domain.shared.errores import DatosInvalidos, RecursoNoEncontrado
from masssend.domain.shared.identificadores import IdPublico
from masssend.domain.shared.paginacion import Cursor, Pagina, PeticionPagina
from masssend.infrastructure.persistence.campanas.models import CampanaFila, ContactoFila
from masssend.infrastructure.persistence.campanas.repositorios import ESTADOS
from masssend.infrastructure.persistence.envio.historial import A_HISTORIAL, DESDE_HISTORIAL
from masssend.infrastructure.persistence.envio.models import MensajeFila
from masssend.infrastructure.persistence.identidad.models import CuentaIdentidad

DIRECCIONES = {Direccion.ENTRANTE: "inbound", Direccion.SALIENTE: "outbound"}


def usuario_de(owner_id: IdPublico) -> int:
    usuario_id = (
        CuentaIdentidad.objects.filter(public_id=owner_id)
        .values_list("usuario_id", flat=True)
        .first()
    )
    if usuario_id is None:
        raise RecursoNoEncontrado("La cuenta no existe.")
    return int(usuario_id)


def _cursor(cursor: Cursor) -> tuple[datetime, str]:
    try:
        fecha, clave = cursor.valores
        return datetime.fromisoformat(fecha), clave
    except ValueError as error:
        raise DatosInvalidos("El cursor no es valido.", "cursor") from error


def _visibles() -> QuerySet[MensajeFila]:
    """Como el sistema actual: los grupos y canales (@g.us, @lid) no se muestran."""
    return MensajeFila.objects.exclude(phone_number__contains="@")


class ConsultasMensajesDjango:
    def mensajes(
        self, owner_id: IdPublico, filtro: FiltroMensajes, peticion: PeticionPagina
    ) -> Pagina[MensajeVista]:
        usuario_id = usuario_de(owner_id)
        nombre = ContactoFila.objects.filter(
            usuario_id=usuario_id, phone_number=OuterRef("phone_number")
        ).values("full_name")[:1]
        consulta = (
            _visibles()
            .filter(usuario_id=usuario_id)
            .select_related("campana")
            .annotate(nombre_contacto=Subquery(nombre))
        )
        if filtro.texto:
            consulta = consulta.filter(
                Q(content__icontains=filtro.texto) | Q(phone_number__contains=filtro.texto)
            )
        if filtro.direccion:
            consulta = consulta.filter(direction=DIRECCIONES[filtro.direccion])
        if filtro.estado:
            consulta = consulta.filter(delivery_status=A_HISTORIAL[filtro.estado])
        if filtro.telefono:
            consulta = consulta.filter(phone_number=filtro.telefono)
        if peticion.cursor is not None:
            fecha, clave = _cursor(peticion.cursor)
            try:
                public_id = UUID(clave)
            except ValueError as error:
                raise DatosInvalidos("El cursor no es valido.", "cursor") from error
            consulta = consulta.filter(
                Q(sent_at__lt=fecha) | Q(sent_at=fecha, public_id__lt=public_id)
            )
        filas = consulta.order_by("-sent_at", "-public_id")[: peticion.limite + 1]
        return Pagina.desde_filas(
            [_mensaje(fila) for fila in filas],
            peticion,
            lambda m: Cursor((m.fecha.isoformat(), str(m.id))),
        )

    def eliminar_mensajes(self, owner_id: IdPublico, ids: Collection[IdPublico]) -> int:
        claves = list(
            MensajeFila.objects.filter(
                usuario_id=usuario_de(owner_id), public_id__in=list(ids)
            ).values_list("id", flat=True)
        )
        # Con el modelo actual: asi los envios que apuntan al mensaje quedan en null.
        _, por_modelo = Message.objects.filter(pk__in=claves).delete()
        return por_modelo.get(Message._meta.label, 0)

    def conversaciones(self, peticion: PeticionPagina) -> Pagina[ConversacionVista]:
        grupos = (
            _visibles()
            .values("phone_number")
            .annotate(ultima=Max("sent_at"), total=Count("id"))
            .order_by("-ultima", "phone_number")
        )
        if peticion.cursor is not None:
            fecha, telefono = _cursor(peticion.cursor)
            grupos = grupos.filter(Q(ultima__lt=fecha) | Q(ultima=fecha, phone_number__gt=telefono))
        pagina = list(grupos[: peticion.limite + 1])
        visibles = pagina[: peticion.limite]
        telefonos = [g["phone_number"] for g in visibles]
        ultimos: dict[str, MensajeFila] = {}
        for fila in (
            _visibles()
            .filter(phone_number__in=telefonos, sent_at__in=[g["ultima"] for g in visibles])
            .order_by("sent_at", "id")
        ):
            ultimos[fila.phone_number] = fila
        nombres = dict(
            ContactoFila.objects.filter(phone_number__in=telefonos)
            .exclude(full_name__isnull=True)
            .exclude(full_name="")
            .values_list("phone_number", "full_name")
        )
        conversaciones = tuple(
            _conversacion(g, ultimos[g["phone_number"]], nombres.get(g["phone_number"]))
            for g in visibles
        )
        siguiente = None
        if len(pagina) > peticion.limite and visibles:
            ultima = visibles[-1]
            siguiente = Cursor((ultima["ultima"].isoformat(), ultima["phone_number"]))
        return Pagina(conversaciones, siguiente)

    def reporte(self, owner_id: IdPublico, periodo: Periodo) -> Reporte:
        usuario_id = usuario_de(owner_id)
        mensajes = _visibles().filter(
            usuario_id=usuario_id,
            sent_at__date__gte=periodo.desde,
            sent_at__date__lte=periodo.hasta,
        )
        saliente = Q(direction="outbound")
        totales = mensajes.aggregate(
            enviados=Count("id", filter=saliente),
            recibidos=Count("id", filter=Q(direction="inbound")),
            entregados=Count("id", filter=saliente & Q(delivery_status="delivered")),
            leidos=Count("id", filter=saliente & Q(delivery_status="read")),
            fallidos=Count("id", filter=saliente & Q(delivery_status="failed")),
            pendientes=Count("id", filter=saliente & Q(delivery_status="pending")),
        )
        por_dia = (
            mensajes.annotate(dia=TruncDate("sent_at"))
            .values("dia")
            .annotate(
                enviados=Count("id", filter=saliente),
                recibidos=Count("id", filter=Q(direction="inbound")),
            )
            .order_by("dia")
        )
        campanas: dict[str, int] = {}
        for estado_db, cantidad in (
            CampanaFila.objects.filter(usuario_id=usuario_id)
            .values_list("status")
            .annotate(cantidad=Count("id"))
            .values_list("status", "cantidad")
        ):
            clave = ESTADOS.get(estado_db)
            if clave is not None:
                campanas[clave.value] = campanas.get(clave.value, 0) + cantidad
        contactos = ContactoFila.objects.filter(usuario_id=usuario_id).aggregate(
            total=Count("id"), de_baja=Count("id", filter=Q(is_opted_out=True))
        )
        return Reporte(
            periodo,
            por_dia=tuple(
                DiaReporte(fila["dia"], fila["enviados"], fila["recibidos"])
                for fila in por_dia
                if fila["dia"]
            ),
            campanas=campanas,
            contactos=contactos["total"],
            contactos_de_baja=contactos["de_baja"],
            **totales,
        )


def _mensaje(fila: Any) -> MensajeVista:
    return MensajeVista(
        IdPublico(fila.public_id),
        fila.phone_number,
        fila.nombre_contacto or fila.phone_number,
        fila.content or "",
        Direccion.ENTRANTE if fila.direction == "inbound" else Direccion.SALIENTE,
        DESDE_HISTORIAL.get(fila.delivery_status, EstadoEntrega.ENVIADO),
        fila.sent_at,
        IdPublico(fila.campana.public_id) if fila.campana else None,
        fila.campana.name if fila.campana else None,
    )


def _conversacion(
    grupo: dict[str, Any], ultimo: MensajeFila, nombre: str | None
) -> ConversacionVista:
    return ConversacionVista(
        grupo["phone_number"],
        nombre or grupo["phone_number"],
        ultimo.content or "",
        Direccion.ENTRANTE if ultimo.direction == "inbound" else Direccion.SALIENTE,
        grupo["ultima"],
        grupo["total"],
    )
