import logging
import uuid

from django.core.cache import cache
from django.db import connection

logger = logging.getLogger(__name__)


class ComprobadorBaseDatos:
    nombre = "base_datos"
    requerida = True

    def comprobar(self) -> bool:
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            return True
        except Exception:
            logger.exception("La base de datos no responde.")
            return False


class ComprobadorCache:
    """La cache es opcional: sin ella la API sigue, sin limites de peticiones."""

    nombre = "cache"
    requerida = False

    def comprobar(self) -> bool:
        clave = f"salud:{uuid.uuid4().hex}"
        try:
            cache.set(clave, "1", timeout=5)
            return cache.get(clave) == "1"
        except Exception:
            logger.exception("La cache no responde.")
            return False
