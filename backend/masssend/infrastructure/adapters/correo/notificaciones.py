import base64
from datetime import datetime
from uuid import UUID

from email_auth.models import EmailTask
from email_auth.repositories import queue_repository
from masssend.application.identidad.puertos import TareaCorreo
from masssend.domain.identidad.notificacion import Notificacion
from masssend.domain.shared.errores import DatosInvalidos
from masssend.domain.shared.identificadores import IdPublico
from masssend.domain.shared.paginacion import Cursor, Pagina, PeticionPagina


class ColaNotificacionesDjango:
    def encolar(self, notificacion: Notificacion, tarea_id: IdPublico) -> None:
        datos: dict[str, object] = {
            "to": notificacion.destinatario,
            "subject": notificacion.asunto,
            "title": notificacion.titulo,
            "message": notificacion.mensaje,
            "signature": notificacion.firma,
        }
        adjunto = notificacion.adjunto
        if adjunto is not None:
            datos["attachment"] = {
                "filename": adjunto.nombre,
                "mimeType": adjunto.tipo,
                "contentBase64": base64.b64encode(adjunto.contenido).decode("ascii"),
            }
        EmailTask.objects.create(
            id=tarea_id,
            task_type=(
                EmailTask.TYPE_ATTACHMENT_NOTIFICATION
                if adjunto
                else EmailTask.TYPE_CUSTOM_NOTIFICATION
            ),
            recipient=notificacion.destinatario,
            subject=notificacion.asunto,
            message=(f"Adjunto: {adjunto.nombre}" if adjunto else notificacion.titulo)[:255],
            payload=datos,
        )

    def tareas(self, peticion: PeticionPagina) -> Pagina[TareaCorreo]:
        # defer: el contenido puede pesar megas y no se expone.
        consulta = EmailTask.objects.defer("payload").order_by("-created_at", "-id")
        if peticion.cursor is not None:
            fecha, tarea_id = _leer_cursor(peticion.cursor)
            consulta = consulta.filter(created_at__lte=fecha).exclude(
                created_at=fecha, id__gte=tarea_id
            )
        filas = list(consulta[: peticion.limite + 1])
        pagina = Pagina.desde_filas(
            filas,
            peticion,
            lambda t: Cursor((t.created_at.isoformat(), str(t.id))),
        )
        return Pagina(
            tuple(
                TareaCorreo(
                    str(t.id),
                    t.task_type,
                    t.recipient,
                    t.subject,
                    t.status,
                    t.attempts,
                    t.error,
                    t.created_at,
                )
                for t in pagina.elementos
            ),
            pagina.siguiente_cursor,
        )

    def pausada(self) -> bool:
        return queue_repository.is_paused()

    def pausar(self) -> None:
        queue_repository.pause_queue()

    def reanudar(self) -> None:
        queue_repository.resume_queue()


def _leer_cursor(cursor: Cursor) -> tuple[datetime, UUID]:
    try:
        fecha, tarea_id = cursor.valores
        return datetime.fromisoformat(fecha), UUID(tarea_id)
    except ValueError as error:
        raise DatosInvalidos("El cursor no es valido.", "cursor") from error
