"""
Worker de la cola de correos. Equivalente Django de src/worker/worker.js.

En la práctica de Node el worker corre con `setInterval` dentro del
mismo proceso del servidor. En Django se prefiere un proceso aparte
para no bloquear el servidor de desarrollo: se ejecuta con

    python manage.py process_email_queue

y queda corriendo en bucle, revisando la cola cada
EMAIL_QUEUE_INTERVAL_MS milisegundos (por defecto 5000), igual que el
worker original. Cada tarea pendiente pasa por
PENDING -> PROCESSING -> SENT/FAILED, exactamente igual que en la
práctica, para poder evidenciarlo en el reporte/demo.
"""
import time

from django.conf import settings
from django.core.management.base import BaseCommand

from email_auth.models import EmailTask
from email_auth.repositories import queue_repository
from email_auth.services.email_sender import default_email_sender


def dispatch_task(task: EmailTask):
    payload = task.payload or {}

    if task.task_type in (EmailTask.TYPE_ACCOUNT_VERIFICATION, EmailTask.TYPE_RESEND_VERIFICATION_CODE):
        return default_email_sender.send_verification_email(
            name=payload.get("name", ""), email=payload.get("email", task.recipient), code=payload.get("code", ""),
        )

    if task.task_type == EmailTask.TYPE_PASSWORD_RECOVERY:
        return default_email_sender.send_recovery_email(
            name=payload.get("name", ""),
            email=payload.get("email", task.recipient),
            reset_url=payload.get("resetUrl", ""),
            expiration_minutes=payload.get("expirationMinutes", 15),
        )

    if task.task_type == EmailTask.TYPE_CUSTOM_NOTIFICATION:
        return default_email_sender.send_custom_message(
            to=payload.get("to", task.recipient),
            subject=payload.get("subject", task.subject),
            title=payload.get("title", ""),
            message=payload.get("message", ""),
            signature=payload.get("signature", "MassSend"),
        )

    if task.task_type == EmailTask.TYPE_ATTACHMENT_NOTIFICATION:
        return default_email_sender.send_attachment_email(
            to=payload.get("to", task.recipient),
            subject=payload.get("subject", task.subject),
            title=payload.get("title", ""),
            message=payload.get("message", ""),
            signature=payload.get("signature", "MassSend"),
            attachment=payload.get("attachment", {}),
        )

    raise ValueError(f"Tipo de tarea no soportado: {task.task_type}")


def process_next_task(stdout) -> bool:
    """Procesa una única tarea pendiente. Devuelve True si procesó algo."""
    task = queue_repository.find_next_pending_task()
    if not task:
        return False

    queue_repository.mark_processing(task)
    stdout.write(f"[worker] Procesando tarea {task.id} ({task.task_type})")

    try:
        dispatch_task(task)
        queue_repository.mark_sent(task)
        stdout.write(f"[worker] Tarea {task.id} enviada correctamente.")
    except Exception as error:  # noqa: BLE001 - se registra en la tarea, no debe tumbar el worker
        queue_repository.mark_failed(task, str(error))
        stdout.write(f"[worker] Falló la tarea {task.id}: {error}")

    return True


class Command(BaseCommand):
    help = "Procesa la cola interna de correos (verificación, MFA, recuperación, notificaciones y adjuntos)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--once", action="store_true",
            help="Procesa únicamente las tareas pendientes actuales y termina (útil para pruebas/CI).",
        )

    def handle(self, *args, **options):
        interval_seconds = getattr(settings, "EMAIL_QUEUE_INTERVAL_MS", 5000) / 1000

        if options["once"]:
            processed_any = False
            while process_next_task(self.stdout):
                processed_any = True
            if not processed_any:
                self.stdout.write("[worker] No había tareas pendientes.")
            return

        self.stdout.write(self.style.SUCCESS(
            f"[worker] Iniciado. Revisa la cola cada {int(interval_seconds * 1000)} ms. Ctrl+C para detener.",
        ))
        try:
            while True:
                process_next_task(self.stdout)
                time.sleep(interval_seconds)
        except KeyboardInterrupt:
            self.stdout.write("[worker] Detenido.")
