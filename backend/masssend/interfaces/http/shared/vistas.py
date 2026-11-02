"""Base de toda vista v1. Agrupa aqui las reglas para no afectar al sistema actual."""

from collections.abc import Callable
from typing import Any

from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import JSONRenderer
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

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
