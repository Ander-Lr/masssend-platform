"""Base de toda vista v1. Agrupa aqui las reglas para no afectar al sistema actual."""

from collections.abc import Callable
from typing import Any

from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import JSONRenderer
from rest_framework.request import Request
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from masssend.domain.shared.errores import DatosInvalidos, NoAutenticado
from masssend.domain.shared.identificadores import IdPublico, id_publico
from masssend.interfaces.http.shared.limites import LimiteAnonimo, LimiteUsuario
from masssend.interfaces.http.shared.problemas import manejar_excepcion


class VistaApi(APIView):
    """Exige JWT por defecto; una vista publica debe declararlo a proposito."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [LimiteAnonimo, LimiteUsuario]
    renderer_classes = [JSONRenderer]

    def get_exception_handler(self) -> Callable[..., Any]:
        return manejar_excepcion


def cuenta_actual(request: Request) -> IdPublico:
    """Identificador publico del token. Un JWT del sistema actual no lo trae."""
    claim = request.auth.get("public_id") if request.auth else None
    if not claim:
        raise NoAutenticado("Inicia sesión en la API v1.")
    try:
        return id_publico(str(claim))
    except DatosInvalidos as error:
        raise NoAutenticado("El token no es válido.") from error
