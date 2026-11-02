"""Envío de notificaciones (correos personalizados) por correo, vía cola. Equivalente de notification.service.js."""
from ..models import EmailTask
from ..repositories import queue_repository
from ..utils.errors import AppError
from ..utils.text import is_valid_email, normalize_email


def send_custom_notification(*, to: str, subject: str, title: str, message: str, signature: str = "") -> dict:
    normalized_email = normalize_email(to)
    clean_subject = (subject or "").strip()
    clean_title = (title or "").strip()
    clean_message = (message or "").strip()
    clean_signature = (signature or "").strip()

    if not normalized_email or not clean_subject or not clean_title or not clean_message:
        raise AppError("El destinatario, el asunto, el título y el mensaje son obligatorios.", 400)

    if not is_valid_email(normalized_email):
        raise AppError("El correo del destinatario es incorrecto.", 400)

    if len(clean_subject) > 120:
        raise AppError("El asunto no puede superar 120 caracteres.", 400)

    if len(clean_title) > 100:
        raise AppError("El título no puede superar 100 caracteres.", 400)

    if len(clean_message) > 3000:
        raise AppError("El mensaje no puede superar 3000 caracteres.", 400)

    final_signature = clean_signature or "MassSend"

    task = queue_repository.enqueue(
        task_type=EmailTask.TYPE_CUSTOM_NOTIFICATION,
        recipient=normalized_email,
        subject=clean_subject,
        message=clean_title,
        payload={
            "to": normalized_email,
            "subject": clean_subject,
            "title": clean_title,
            "message": clean_message,
            "signature": final_signature,
        },
    )

    return {
        "message": "El correo se registró en la cola y se enviará en un momento.",
        "recipient": normalized_email,
        "taskId": str(task.id),
    }
