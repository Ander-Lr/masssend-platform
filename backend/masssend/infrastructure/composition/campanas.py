"""Contenedor del modulo de campanas."""

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
from masssend.infrastructure.composition.root import contenedor as raiz
from masssend.infrastructure.persistence.campanas.repositorios import RepoContactosDjango


class ContenedorCampanas:
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


contenedor_campanas = ContenedorCampanas()
