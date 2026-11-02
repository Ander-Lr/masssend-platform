"""
Endpoints de registro + verificación de cuenta por código.
Equivalente Django de auth.controller.js / auth.routes.js.

Las vistas son intencionalmente "delgadas": solo leen el request y
delegan toda la lógica de negocio a verification_service (principio
de responsabilidad única). Cualquier error de negocio se lanza como
AppError, que ya es una APIException de DRF, así que basta con
dejarla propagar para que DRF construya la respuesta de error.

Estos endpoints identifican al usuario por el correo que viene en el
body/URL, no por `request.user`. Se desactiva la autenticación por
sesión de DRF (@authentication_classes([])) para que una cookie de
sesión vieja en el navegador (p.ej. de un login anterior con Google)
no dispare el chequeo CSRF de SessionAuthentication en estas rutas
públicas.
"""
from rest_framework.decorators import api_view, authentication_classes
from rest_framework.response import Response

from ..services import verification_service


@api_view(["POST"])
@authentication_classes([])
def register(request):
    result = verification_service.register_user(
        name=request.data.get("name"),
        email=request.data.get("email"),
        password=request.data.get("password"),
    )
    return Response(result, status=201)


@api_view(["POST"])
@authentication_classes([])
def verify(request):
    result = verification_service.verify_account(
        email=request.data.get("email"),
        code=request.data.get("code"),
    )
    return Response(result, status=200)


@api_view(["POST"])
@authentication_classes([])
def resend(request):
    result = verification_service.resend_verification_code(request.data.get("email"))
    return Response(result, status=200)


@api_view(["GET"])
@authentication_classes([])
def status(request, email):
    result = verification_service.get_account_status(email)
    return Response(result, status=200)
