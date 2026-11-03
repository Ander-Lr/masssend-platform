"""Casos de uso de la libreta de contactos, trasladados de mass_sender/views.py."""

from collections.abc import Mapping
from dataclasses import dataclass

from masssend.application.shared.puertos import IGeneradorIds, IUnidadDeTrabajo
from masssend.domain.campanas.contacto import Contacto
from masssend.domain.campanas.repositorios import FiltroContactos, IRepoContactos
from masssend.domain.campanas.telefono import Telefono
from masssend.domain.shared.identificadores import IdPublico
from masssend.domain.shared.paginacion import Pagina, PeticionPagina


@dataclass(frozen=True, slots=True)
class ContactoGuardado:
    contacto: Contacto
    creado: bool


@dataclass(frozen=True, slots=True)
class CambiosContacto:
    """Solo se aplica lo que no es None, como en el PUT del sistema actual."""

    nombre: str | None = None
    etiquetas: str | None = None
    datos: Mapping[str, str] | None = None
    dado_de_baja: bool | None = None


class GuardarContacto:
    """Si el dueno ya tiene ese numero, actualiza sus datos en lugar de duplicarlo."""

    def __init__(
        self, contactos: IRepoContactos, ids: IGeneradorIds, uow: IUnidadDeTrabajo
    ) -> None:
        self._contactos = contactos
        self._ids = ids
        self._uow = uow

    def ejecutar(
        self, owner_id: IdPublico, telefono: str, nombre: str = "", etiquetas: str = ""
    ) -> ContactoGuardado:
        numero = Telefono.desde_texto(telefono)
        with self._uow:
            existente = self._contactos.buscar_por_telefonos(owner_id, [numero]).get(numero)
            if existente is None:
                nuevo = Contacto.nuevo(self._ids.nuevo(), owner_id, numero, nombre, etiquetas)
                self._contactos.guardar(nuevo)
                return ContactoGuardado(nuevo, creado=True)
            existente.renombrar(nombre)
            existente.etiquetar(etiquetas)
            self._contactos.guardar(existente)
            return ContactoGuardado(existente, creado=False)


class ObtenerContacto:
    def __init__(self, contactos: IRepoContactos) -> None:
        self._contactos = contactos

    def ejecutar(self, owner_id: IdPublico, contacto_id: IdPublico) -> Contacto:
        return self._contactos.obtener(owner_id, contacto_id)


class ListarContactos:
    def __init__(self, contactos: IRepoContactos) -> None:
        self._contactos = contactos

    def ejecutar(
        self,
        owner_id: IdPublico,
        filtro: FiltroContactos | None = None,
        peticion: PeticionPagina | None = None,
    ) -> Pagina[Contacto]:
        return self._contactos.listar(
            owner_id, filtro or FiltroContactos(), peticion or PeticionPagina()
        )


class EditarContacto:
    """El telefono no se edita: es la identidad del contacto en la libreta."""

    def __init__(self, contactos: IRepoContactos, uow: IUnidadDeTrabajo) -> None:
        self._contactos = contactos
        self._uow = uow

    def ejecutar(
        self, owner_id: IdPublico, contacto_id: IdPublico, cambios: CambiosContacto
    ) -> Contacto:
        with self._uow:
            contacto = self._contactos.obtener(owner_id, contacto_id)
            if cambios.nombre is not None:
                contacto.renombrar(cambios.nombre)
            if cambios.etiquetas is not None:
                contacto.etiquetar(cambios.etiquetas)
            if cambios.datos is not None:
                contacto.completar_datos(cambios.datos)
            if cambios.dado_de_baja is True:
                contacto.dar_de_baja()
            elif cambios.dado_de_baja is False:
                contacto.reactivar()
            self._contactos.guardar(contacto)
            return contacto


class EliminarContacto:
    def __init__(self, contactos: IRepoContactos, uow: IUnidadDeTrabajo) -> None:
        self._contactos = contactos
        self._uow = uow

    def ejecutar(self, owner_id: IdPublico, contacto_id: IdPublico) -> None:
        with self._uow:
            self._contactos.eliminar(owner_id, contacto_id)
