# backend/mass_sender/middleware.py
import logging
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

logger = logging.getLogger(__name__)


class JWTAuthMiddleware:
    """
    Middleware que lee el JWT del header Authorization y autentica
    al usuario en request.user para todas las vistas Django.
    Si ya hay sesión activa, no hace nada.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            auth_header = request.headers.get('Authorization', '')
            if auth_header.startswith('Bearer '):
                try:
                    jwt_auth = JWTAuthentication()
                    result = jwt_auth.authenticate(request)
                    if result:
                        user, token = result
                        request.user = user
                        logger.debug(f"JWT middleware: usuario autenticado como {user.username}")
                except (InvalidToken, TokenError) as e:
                    logger.warning(f"JWT middleware: token inválido — {e}")
                except Exception as e:
                    logger.error(f"JWT middleware: error inesperado — {e}")

        return self.get_response(request)
