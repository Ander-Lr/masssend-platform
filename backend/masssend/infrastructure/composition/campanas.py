"""Contenedor del modulo de campanas."""

from django.conf import settings

from masssend.application.campanas.campanas import (
    CrearCampana,
    DescargarAdjunto,
    EditarCampana,
    EliminarCampana,
    ListarCampanas,
    ObtenerCampana,
    SubirAdjunto,
)
from masssend.application.campanas.contactos import (
    EditarContacto,
    EliminarContacto,
    EliminarContactos,
    GuardarContacto,
    ListarContactos,
    ListarEtiquetas,
    ObtenerContacto,
)
from masssend.application.campanas.importacion import ImportarContactos
from masssend.application.campanas.puertos import IAlmacenArchivos
from masssend.infrastructure.adapters.archivos.memoria import AlmacenMemoria
from masssend.infrastructure.adapters.archivos.pocketbase import AlmacenPocketBase
from masssend.infrastructure.composition.root import contenedor as raiz
from masssend.infrastructure.persistence.campanas.repositorios import (
    RepoCampanasDjango,
    RepoContactosDjango,
)


def _repos() -> tuple[RepoCampanasDjango, RepoContactosDjango]:
    contactos = RepoContactosDjango()
    return RepoCampanasDjango(contactos), contactos


class ContenedorCampanas:
    def almacen(self) -> IAlmacenArchivos:
        """ALMACEN_ARCHIVOS elige el adaptador: memoria en ci, pocketbase en real."""
        if settings.ALMACEN_ARCHIVOS == "memoria":
            return AlmacenMemoria()
        return AlmacenPocketBase()

    # Contactos
    def guardar_contacto(self) -> GuardarContacto:
        return GuardarContacto(
            RepoContactosDjango(), raiz.generador_ids(), raiz.unidad_de_trabajo()
        )

    def obtener_contacto(self) -> ObtenerContacto:
        return ObtenerContacto(RepoContactosDjango())

    def listar_contactos(self) -> ListarContactos:
        return ListarContactos(RepoContactosDjango())

    def editar_contacto(self) -> EditarContacto:
        return EditarContacto(RepoContactosDjango(), raiz.unidad_de_trabajo())

    def eliminar_contacto(self) -> EliminarContacto:
        return EliminarContacto(RepoContactosDjango(), raiz.unidad_de_trabajo())

    def eliminar_contactos(self) -> EliminarContactos:
        return EliminarContactos(RepoContactosDjango(), raiz.unidad_de_trabajo())

    def listar_etiquetas(self) -> ListarEtiquetas:
        return ListarEtiquetas(RepoContactosDjango())

    def importar_contactos(self) -> ImportarContactos:
        """Cada lote abre su propia transaccion: un fallo no deshace los anteriores."""
        return ImportarContactos(
            RepoContactosDjango(), raiz.generador_ids(), raiz.unidad_de_trabajo()
        )

    # Campanas
    def crear_campana(self) -> CrearCampana:
        campanas, contactos = _repos()
        return CrearCampana(campanas, contactos, raiz.generador_ids(), raiz.unidad_de_trabajo())

    def obtener_campana(self) -> ObtenerCampana:
        return ObtenerCampana(*_repos())

    def listar_campanas(self) -> ListarCampanas:
        return ListarCampanas(RepoCampanasDjango())

    def editar_campana(self) -> EditarCampana:
        return EditarCampana(*_repos(), raiz.unidad_de_trabajo())

    def eliminar_campana(self) -> EliminarCampana:
        return EliminarCampana(RepoCampanasDjango(), raiz.unidad_de_trabajo())

    def subir_adjunto(self) -> SubirAdjunto:
        return SubirAdjunto(*_repos(), self.almacen(), raiz.unidad_de_trabajo())

    def descargar_adjunto(self) -> DescargarAdjunto:
        return DescargarAdjunto(RepoCampanasDjango(), self.almacen())


contenedor_campanas = ContenedorCampanas()
