"""Repositorios de envios y lanzamientos."""

from collections.abc import Sequence
from datetime import datetime, timedelta

from django.db.models import Count, F

from mass_sender.models import Message
from masssend.domain.envio.envio import Envio, EstadoEnvio, Progreso
from masssend.domain.envio.lanzamiento import Lanzamiento
from masssend.domain.shared.identificadores import IdPublico
from masssend.infrastructure.persistence.campanas.models import CampanaFila
from masssend.infrastructure.persistence.envio.models import EnvioFila, LanzamientoFila
from masssend.infrastructure.persistence.identidad.models import CuentaIdentidad

# Estado del mensaje en el sistema actual: los reportes actuales lo leen de ahi.
ESTADO_MENSAJE = {EstadoEnvio.ENVIADO: "sent", EstadoEnvio.FALLIDO: "failed"}


def _envio(fila: EnvioFila) -> Envio:
    return Envio(
        IdPublico(fila.id),
        IdPublico(fila.campana_id),
        IdPublico(fila.owner_id),
        IdPublico(fila.contacto_id),
        fila.telefono,
        fila.orden,
        EstadoEnvio(fila.estado),
        fila.id_externo,
        fila.detalle,
        fila.texto,
    )


class RepoEnviosDjango:
    def agregar_varios(self, envios: Sequence[Envio]) -> None:
        EnvioFila.objects.bulk_create(
            [
                EnvioFila(
                    id=e.id,
                    campana_id=e.campana_id,
                    owner_id=e.owner_id,
                    contacto_id=e.contacto_id,
                    telefono=e.telefono,
                    orden=e.orden,
                    estado=e.estado.value,
                )
                for e in envios
            ],
            batch_size=500,
        )

    def bloquear(self, envio_id: IdPublico) -> Envio | None:
        fila = EnvioFila.objects.select_for_update().filter(pk=envio_id).first()
        return _envio(fila) if fila else None

    def guardar(self, envio: Envio) -> None:
        fila = EnvioFila.objects.get(pk=envio.id)
        fila.estado = envio.estado.value
        fila.id_externo = envio.id_externo
        fila.detalle = envio.detalle
        fila.texto = envio.texto
        if envio.estado in ESTADO_MENSAJE and fila.mensaje_id is None:
            fila.mensaje = self._mensaje_actual(envio)
        fila.save()

    @staticmethod
    def _mensaje_actual(envio: Envio) -> Message:
        """Registra el mensaje donde lo buscan las pantallas y reportes actuales."""
        usuario_id = (
            CuentaIdentidad.objects.filter(public_id=envio.owner_id)
            .values_list("usuario_id", flat=True)
            .first()
        )
        campana_pk = (
            CampanaFila.objects.filter(public_id=envio.campana_id)
            .values_list("id", flat=True)
            .first()
        )
        return Message.objects.create(
            owner_id=usuario_id,
            campaign_id=campana_pk,
            phone_number=envio.telefono,
            direction="outbound",
            content=envio.texto or "",
            delivery_status=ESTADO_MENSAJE[envio.estado],
            wpp_message_id=envio.id_externo,
            error_log=envio.detalle,
        )

    def cancelar_pendientes(self, campana_id: IdPublico) -> int:
        return EnvioFila.objects.filter(
            campana_id=campana_id, estado=EstadoEnvio.PENDIENTE.value
        ).update(estado=EstadoEnvio.CANCELADO.value)

    def progreso(self, campana_id: IdPublico) -> Progreso:
        conteo = dict(
            EnvioFila.objects.filter(campana_id=campana_id)
            .values_list("estado")
            .annotate(cantidad=Count("id"))
            .values_list("estado", "cantidad")
        )
        return Progreso(
            total=sum(conteo.values()),
            enviados=conteo.get(EstadoEnvio.ENVIADO.value, 0),
            fallidos=conteo.get(EstadoEnvio.FALLIDO.value, 0),
            omitidos=conteo.get(EstadoEnvio.OMITIDO.value, 0),
            cancelados=conteo.get(EstadoEnvio.CANCELADO.value, 0),
        )

    # Usados por la cola en base de datos y el trabajador, no por los casos de uso.

    @staticmethod
    def programar_desde(inicio: datetime, retrasos: dict[IdPublico, int]) -> None:
        """Programa muchos envios con una consulta por lote."""
        filas = [EnvioFila(id=envio_id) for envio_id in retrasos]
        for fila in filas:
            fila.programado_para = inicio + timedelta(seconds=retrasos[IdPublico(fila.id)])
        EnvioFila.objects.bulk_update(filas, ["programado_para"], batch_size=500)

    @staticmethod
    def siguiente_vencido(ahora: datetime) -> IdPublico | None:
        envio_id = (
            EnvioFila.objects.filter(estado=EstadoEnvio.PENDIENTE.value, programado_para__lte=ahora)
            .order_by(F("programado_para").asc(), "orden")
            .values_list("id", flat=True)
            .first()
        )
        return IdPublico(envio_id) if envio_id else None


class RepoLanzamientosDjango:
    def agregar(self, lanzamiento: Lanzamiento) -> None:
        LanzamientoFila.objects.create(
            campana_id=lanzamiento.campana_id,
            owner_id=lanzamiento.owner_id,
            reserva_id=lanzamiento.reserva_id,
            total=lanzamiento.total,
        )

    def obtener(self, campana_id: IdPublico) -> Lanzamiento | None:
        fila = LanzamientoFila.objects.filter(pk=campana_id).first()
        if fila is None:
            return None
        return Lanzamiento(
            IdPublico(fila.campana_id),
            IdPublico(fila.owner_id),
            IdPublico(fila.reserva_id),
            fila.total,
        )
