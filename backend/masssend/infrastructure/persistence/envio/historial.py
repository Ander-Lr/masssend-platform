"""Historial de mensajes sobre la tabla messages del sistema actual.

Conserva lo que hacian api_webhook, api_message_ack y api_send_result, para
que el chat y los reportes actuales sigan viendo lo mismo.
"""

from mass_sender.models import Contact, Message
from masssend.domain.envio.entrega import EstadoEntrega, avanza
from masssend.domain.shared.errores import RecursoNoEncontrado
from masssend.domain.shared.identificadores import IdPublico
from masssend.infrastructure.persistence.envio.models import MensajeFila
from masssend.infrastructure.persistence.identidad.models import CuentaIdentidad

A_HISTORIAL = {
    EstadoEntrega.PENDIENTE: "pending",
    EstadoEntrega.ENVIADO: "sent",
    EstadoEntrega.ENTREGADO: "delivered",
    EstadoEntrega.LEIDO: "read",
    EstadoEntrega.FALLIDO: "failed",
}
DESDE_HISTORIAL = {valor: estado for estado, valor in A_HISTORIAL.items()}


def _dueno_conversacion(numero: str) -> int | None:
    """Igual que el sistema actual: es de quien le escribio por ultima vez."""
    return (
        Message.objects.filter(phone_number=numero, direction="outbound", owner__isnull=False)
        .order_by("-sent_at")
        .values_list("owner_id", flat=True)
        .first()
    )


class HistorialMensajesDjango:
    def registrar_entrante(self, telefono: str, texto: str, id_externo: str | None) -> bool:
        if (
            id_externo
            and Message.objects.filter(direction="inbound", wpp_message_id=id_externo).exists()
        ):
            return False
        dueno = _dueno_conversacion(telefono)
        Contact.objects.get_or_create(
            phone_number=telefono, owner_id=dueno, defaults={"full_name": telefono}
        )
        Message.objects.create(
            owner_id=dueno,
            phone_number=telefono,
            content=texto,
            direction="inbound",
            wpp_message_id=id_externo,
        )
        return True

    def registrar_acuse(self, id_externo: str, estado: EstadoEntrega) -> int:
        cambiados = 0
        for mensaje in Message.objects.select_for_update().filter(
            wpp_message_id=id_externo, direction="outbound"
        ):
            actual = DESDE_HISTORIAL.get(mensaje.delivery_status, EstadoEntrega.PENDIENTE)
            if avanza(actual, estado):
                mensaje.delivery_status = A_HISTORIAL[estado]
                mensaje.save(update_fields=["delivery_status"])
                cambiados += 1
        return cambiados

    def registrar_resultado_sin_envio(
        self, telefono: str, enviado: bool, id_externo: str | None, motivo: str | None
    ) -> int:
        """La cola del gateway es FIFO: corresponde al pendiente mas antiguo del numero."""
        mensaje = (
            Message.objects.select_for_update()
            .filter(phone_number=telefono, direction="outbound", delivery_status="pending")
            .order_by("sent_at", "id")
            .first()
        )
        if mensaje is None:
            return 0
        mensaje.delivery_status = "sent" if enviado else "failed"
        if not enviado:
            mensaje.error_log = (motivo or "")[:500]
        if id_externo and not mensaje.wpp_message_id:
            mensaje.wpp_message_id = id_externo
        mensaje.save()
        return 1

    def registrar_saliente(self, owner_id: IdPublico, telefono: str, texto: str) -> IdPublico:
        """Como MessageService.enviar_mensaje: contacto y mensaje pendiente del staff."""
        usuario_id = (
            CuentaIdentidad.objects.filter(public_id=owner_id)
            .values_list("usuario_id", flat=True)
            .first()
        )
        if usuario_id is None:
            raise RecursoNoEncontrado("La cuenta no existe.")
        Contact.objects.get_or_create(
            phone_number=telefono, owner_id=usuario_id, defaults={"full_name": telefono}
        )
        mensaje = Message.objects.create(
            owner_id=usuario_id,
            phone_number=telefono,
            content=texto,
            direction="outbound",
            delivery_status="pending",
        )
        # La base genera el public_id al insertar.
        return IdPublico(MensajeFila.objects.values_list("public_id", flat=True).get(pk=mensaje.pk))

    def registrar_resultado_de_mensaje(
        self, mensaje_id: IdPublico, enviado: bool, id_externo: str | None, motivo: str | None
    ) -> int:
        cambios: dict[str, object] = {"delivery_status": "sent" if enviado else "failed"}
        if enviado and id_externo:
            cambios["wpp_message_id"] = id_externo
        if not enviado:
            cambios["error_log"] = (motivo or "")[:500]
        return MensajeFila.objects.filter(
            public_id=mensaje_id, direction="outbound", delivery_status="pending"
        ).update(**cambios)
