"""Almacen en memoria del proceso, para el perfil ci y las pruebas.

Los archivos se pierden al reiniciar. El perfil ci usa un solo worker,
asi que todas las peticiones ven el mismo almacen.
"""

import threading
import uuid

from masssend.application.campanas.puertos import ArchivoDescargado
from masssend.domain.campanas.archivo import ArchivoCampana
from masssend.domain.shared.identificadores import IdPublico

PREFIJO = "memoria://"
_archivos: dict[str, ArchivoDescargado] = {}
_candado = threading.Lock()


class AlmacenMemoria:
    def guardar(self, archivo: ArchivoCampana, owner_id: IdPublico, campana_id: IdPublico) -> str:
        referencia = f"{PREFIJO}{campana_id}/{uuid.uuid4().hex}/{archivo.nombre}"
        with _candado:
            _archivos[referencia] = ArchivoDescargado(
                archivo.nombre, archivo.tipo, archivo.contenido
            )
        return referencia

    def obtener(self, referencia: str) -> ArchivoDescargado | None:
        if not referencia.startswith(PREFIJO):
            return None
        with _candado:
            return _archivos.get(referencia)
