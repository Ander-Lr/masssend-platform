"""
Repositorio de la cola interna de correos (EmailTask) y su bandera de
pausa (QueueControl). Equivalente Django de `queue.service.js`.
"""
from django.conf import settings
from django.utils import timezone

from ..models import EmailTask, QueueControl


def enqueue(*, task_type: str, recipient: str, subject: str, message: str, payload: dict) -> EmailTask:
    return EmailTask.objects.create(
        task_type=task_type,
        recipient=recipient,
        subject=subject,
        message=message[:255],
        payload=payload or {},
    )


def get_all_tasks():
    return EmailTask.objects.all().order_by("created_at")


def get_task_by_id(task_id):
    return EmailTask.objects.filter(pk=task_id).first()


def find_next_pending_task():
    if is_paused():
        return None
    return EmailTask.objects.filter(status=EmailTask.STATUS_PENDING).order_by("created_at").first()


def mark_processing(task: EmailTask):
    task.status = EmailTask.STATUS_PROCESSING
    task.error = None
    task.save(update_fields=["status", "error", "updated_at"])
    return task


def mark_sent(task: EmailTask):
    task.status = EmailTask.STATUS_SENT
    task.error = None
    task.save(update_fields=["status", "error", "updated_at"])
    return task


def mark_failed(task: EmailTask, error_message: str):
    task.attempts += 1
    max_attempts = getattr(settings, "EMAIL_QUEUE_MAX_ATTEMPTS", 3)
    task.status = EmailTask.STATUS_PENDING if task.attempts < max_attempts else EmailTask.STATUS_FAILED
    task.error = error_message
    task.save(update_fields=["attempts", "status", "error", "updated_at"])
    return task


def is_paused() -> bool:
    return QueueControl.get_solo().paused


def pause_queue():
    control = QueueControl.get_solo()
    control.paused = True
    control.save(update_fields=["paused"])
    return control


def resume_queue():
    control = QueueControl.get_solo()
    control.paused = False
    control.save(update_fields=["paused"])
    return control
