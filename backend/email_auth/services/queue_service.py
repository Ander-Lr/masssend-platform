"""Consulta y control (pausar/reanudar) de la cola interna de correos."""
from ..repositories import queue_repository


def list_tasks() -> dict:
    tasks = [
        {
            "id": str(task.id),
            "type": task.task_type,
            "to": task.recipient,
            "subject": task.subject,
            "message": task.message,
            "status": task.status,
            "attempts": task.attempts,
            "error": task.error,
            "createdAt": task.created_at.isoformat(),
            "updatedAt": task.updated_at.isoformat(),
        }
        for task in queue_repository.get_all_tasks()
    ]
    return {"paused": queue_repository.is_paused(), "tasks": tasks}


def pause_queue() -> dict:
    queue_repository.pause_queue()
    return {"message": "La cola fue pausada. El worker dejará de tomar tareas nuevas.", "paused": True}


def resume_queue() -> dict:
    queue_repository.resume_queue()
    return {"message": "La cola fue reanudada. El worker continuará procesando tareas.", "paused": False}
