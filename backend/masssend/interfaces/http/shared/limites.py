"""Limites de peticiones de la v1."""

import logging
from typing import Any

from rest_framework.request import Request
from rest_framework.throttling import AnonRateThrottle, SimpleRateThrottle, UserRateThrottle

logger = logging.getLogger(__name__)


class _SinBloquearSiFallaLaCache:
    """Si Redis cae se deja pasar: es mejor perder el limite que toda la API."""

    def allow_request(self, request: Request, view: Any) -> bool:
        try:
            return super().allow_request(request, view)  # type: ignore[misc,no-any-return]
        except Exception:
            logger.exception("No se pudo revisar el limite de peticiones.")
            return True


class LimiteAnonimo(_SinBloquearSiFallaLaCache, AnonRateThrottle):
    scope = "anonimo_v1"


class LimiteUsuario(_SinBloquearSiFallaLaCache, UserRateThrottle):
    scope = "usuario_v1"


class LimiteSensible(_SinBloquearSiFallaLaCache, SimpleRateThrottle):
    """Frena la fuerza bruta por IP en rutas de credenciales, con o sin sesion."""

    scope = "sensible_v1"

    def get_cache_key(self, request: Request, view: Any) -> str:
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class LimiteAsistente(_SinBloquearSiFallaLaCache, UserRateThrottle):
    """Cada consulta ocupa el modelo varios segundos."""

    scope = "asistente_v1"
