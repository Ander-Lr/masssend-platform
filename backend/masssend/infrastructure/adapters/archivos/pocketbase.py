"""Adaptador de PocketBase sobre mass_sender/pocketbase_media.py.

Reutiliza la logica actual: coleccion privada, archivo protegido y descarga
solo con el superusuario. La referencia guardada es la misma URL que usa el
sistema actual, asi que una campana sirve en las dos versiones.
"""

from django.core.files.base import ContentFile

from mass_sender import pocketbase_media
from masssend.application.campanas.puertos import ArchivoDescargado
from masssend.domain.campanas.archivo import ArchivoCampana
from masssend.domain.shared.errores import ServicioNoDisponible
from masssend.domain.shared.identificadores import IdPublico

NO_DISPONIBLE = "El almacén de archivos no está disponible. Intenta más tarde."


class AlmacenPocketBase:
    def guardar(self, archivo: ArchivoCampana, owner_id: IdPublico, campana_id: IdPublico) -> str:
        contenido = ContentFile(archivo.contenido, name=archivo.nombre)
        contenido.content_type = archivo.tipo  # type: ignore[attr-defined]
        url = pocketbase_media.subir_media_campana(contenido, title=str(campana_id))
        if not url:
            raise ServicioNoDisponible(NO_DISPONIBLE)
        return str(url)

    def obtener(self, referencia: str) -> ArchivoDescargado | None:
        if not pocketbase_media.es_url_pocketbase(referencia):
            return None
        contenido, tipo = pocketbase_media.descargar_media(referencia)
        if contenido is None:
            raise ServicioNoDisponible(NO_DISPONIBLE)
        return ArchivoDescargado(referencia.rsplit("/", 1)[-1], tipo, contenido)
