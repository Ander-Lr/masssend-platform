"""
Consulta y control de la cola interna de correos. Equivalente Django
de queue.controller.js / queue.routes.js.

Se restringe a usuarios staff (IsAdminUser) porque pausar la cola o
ver todas las tareas encoladas (incluye payloads con adjuntos/base64)
es una operación administrativa, no algo que deba exponerse público.
"""
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from ..services import queue_service


@api_view(["GET"])
@authentication_classes([JWTAuthentication, SessionAuthentication])
@permission_classes([IsAdminUser])
def list_tasks(request):
    return Response(queue_service.list_tasks(), status=200)


@api_view(["POST"])
@authentication_classes([JWTAuthentication, SessionAuthentication])
@permission_classes([IsAdminUser])
def pause_queue(request):
    return Response(queue_service.pause_queue(), status=200)


@api_view(["POST"])
@authentication_classes([JWTAuthentication, SessionAuthentication])
@permission_classes([IsAdminUser])
def resume_queue(request):
    return Response(queue_service.resume_queue(), status=200)
