"""Recuperación de contraseña. Equivalente Django de recovery.controller.js / recovery.routes.js."""
from rest_framework.decorators import api_view, authentication_classes
from rest_framework.response import Response

from ..services import recovery_service


@api_view(["POST"])
@authentication_classes([])
def request_recovery(request):
    result = recovery_service.request_account_recovery(request.data.get("email"))
    return Response(result, status=202)


@api_view(["GET"])
@authentication_classes([])
def validate_token(request):
    result = recovery_service.validate_recovery_token(
        email=request.query_params.get("email"),
        token=request.query_params.get("token"),
    )
    return Response(result, status=200)


@api_view(["POST"])
@authentication_classes([])
def reset_password(request):
    result = recovery_service.reset_password(
        email=request.data.get("email"),
        token=request.data.get("token"),
        new_password=request.data.get("newPassword"),
    )
    return Response(result, status=200)
