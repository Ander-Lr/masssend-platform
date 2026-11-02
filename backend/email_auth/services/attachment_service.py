"""
Envío de correos con archivo adjunto, vía cola. Equivalente de
attachment.service.js. Django ya recibe el multipart/form-data de
forma nativa (request.FILES), así que no se necesita un equivalente
de multer/upload.config.js.
"""
import base64

from django.conf import settings

from ..models import EmailTask
from ..repositories import queue_repository
from ..utils.errors import AppError
from ..utils.text import is_valid_email, normalize_email

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "image/png",
    "image/jpeg",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def send_attachment_notification(*, to: str, subject: str, title: str, message: str, signature: str, file) -> dict:
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

    if not file:
        raise AppError("Debes adjuntar un archivo.", 400)

    if file.content_type not in ALLOWED_MIME_TYPES:
        raise AppError("El tipo de archivo no está permitido. Usa PDF, DOCX, PNG, JPG o XLSX.", 400)

    max_size_bytes = settings.EMAIL_MAX_ATTACHMENT_SIZE_MB * 1024 * 1024
    if file.size > max_size_bytes:
        raise AppError(
            f"El archivo supera el tamaño máximo permitido de {settings.EMAIL_MAX_ATTACHMENT_SIZE_MB} MB.", 413,
        )

    file_bytes = file.read()

    task = queue_repository.enqueue(
        task_type=EmailTask.TYPE_ATTACHMENT_NOTIFICATION,
        recipient=normalized_email,
        subject=clean_subject,
        message=f"Adjunto: {file.name}",
        payload={
            "to": normalized_email,
            "subject": clean_subject,
            "title": clean_title,
            "message": clean_message,
            "signature": clean_signature or "MassSend",
            "attachment": {
                "filename": file.name,
                "mimeType": file.content_type,
                "contentBase64": base64.b64encode(file_bytes).decode("ascii"),
            },
        },
    )

    return {
        "message": "El archivo se registró en la cola y se enviará en un momento.",
        "taskId": str(task.id),
        "fileName": file.name,
        "fileSizeBytes": file.size,
    }
