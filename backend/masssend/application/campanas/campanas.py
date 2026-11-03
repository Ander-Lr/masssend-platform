"""Casos de uso de campanas y su adjunto, trasladados de mass_sender/views.py."""

from collections.abc import Iterable
from dataclasses import dataclass

from masssend.application.campanas.puertos import ArchivoDescargado, IAlmacenArchivos
from masssend.application.shared.puertos import IGeneradorIds, IUnidadDeTrabajo
from masssend.domain.campanas.archivo import ArchivoCampana
from masssend.domain.campanas.campana import Campana
from masssend.domain.campanas.repositorios import FiltroCampanas, IRepoCampanas, IRepoContactos
from masssend.domain.shared.errores import RecursoNoEncontrado
from masssend.domain.shared.identificadores import IdPublico
from masssend.domain.shared.paginacion import Pagina, PeticionPagina


@dataclass(frozen=True, slots=True)
class DetalleCampana:
    campana: Campana
    destinatarios: int


@dataclass(frozen=True, slots=True)
class CambiosCampana:
    """Solo se aplica lo que no es None."""

    nombre: str | None = None
    mensaje: str | None = None
    etiquetas: str | Iterable[str] | None = None


class _ConDestinatarios:
    def __init__(self, contactos: IRepoContactos) -> None:
        self._contactos = contactos

    def _detalle(self, campana: Campana) -> DetalleCampana:
        total = self._contactos.contar_destinatarios(campana.owner_id, campana.etiquetas)
        return DetalleCampana(campana, total)


class CrearCampana(_ConDestinatarios):
    def __init__(
        self,
        campanas: IRepoCampanas,
        contactos: IRepoContactos,
        ids: IGeneradorIds,
        uow: IUnidadDeTrabajo,
    ) -> None:
        super().__init__(contactos)
        self._campanas = campanas
        self._ids = ids
        self._uow = uow

    def ejecutar(
        self,
        owner_id: IdPublico,
        nombre: str,
        mensaje: str,
        etiquetas: str | Iterable[str] = (),
    ) -> DetalleCampana:
        campana = Campana.nueva(self._ids.nuevo(), owner_id, nombre, mensaje, etiquetas)
        with self._uow:
            self._campanas.guardar(campana)
        return self._detalle(campana)


class ObtenerCampana(_ConDestinatarios):
    def __init__(self, campanas: IRepoCampanas, contactos: IRepoContactos) -> None:
        super().__init__(contactos)
        self._campanas = campanas

    def ejecutar(self, owner_id: IdPublico, campana_id: IdPublico) -> DetalleCampana:
        return self._detalle(self._campanas.obtener(owner_id, campana_id))


class ListarCampanas:
    def __init__(self, campanas: IRepoCampanas) -> None:
        self._campanas = campanas

    def ejecutar(
        self,
        owner_id: IdPublico,
        filtro: FiltroCampanas | None = None,
        peticion: PeticionPagina | None = None,
    ) -> Pagina[Campana]:
        return self._campanas.listar(
            owner_id, filtro or FiltroCampanas(), peticion or PeticionPagina()
        )


class EditarCampana(_ConDestinatarios):
    def __init__(
        self, campanas: IRepoCampanas, contactos: IRepoContactos, uow: IUnidadDeTrabajo
    ) -> None:
        super().__init__(contactos)
        self._campanas = campanas
        self._uow = uow

    def ejecutar(
        self, owner_id: IdPublico, campana_id: IdPublico, cambios: CambiosCampana
    ) -> DetalleCampana:
        with self._uow:
            campana = self._campanas.bloquear(owner_id, campana_id)
            campana.editar(cambios.nombre, cambios.mensaje, cambios.etiquetas)
            self._campanas.guardar(campana)
        return self._detalle(campana)


class EliminarCampana:
    def __init__(self, campanas: IRepoCampanas, uow: IUnidadDeTrabajo) -> None:
        self._campanas = campanas
        self._uow = uow

    def ejecutar(self, owner_id: IdPublico, campana_id: IdPublico) -> None:
        with self._uow:
            campana = self._campanas.bloquear(owner_id, campana_id)
            campana.exigir_eliminable()
            self._campanas.eliminar(owner_id, campana_id)


class SubirAdjunto(_ConDestinatarios):
    """El archivo se valida y se guarda antes de abrir la transaccion.

    Si mientras tanto la campana dejo de ser borrador, el archivo queda
    huerfano en el almacen, pero la campana nunca queda a medias.
    """

    def __init__(
        self,
        campanas: IRepoCampanas,
        contactos: IRepoContactos,
        almacen: IAlmacenArchivos,
        uow: IUnidadDeTrabajo,
    ) -> None:
        super().__init__(contactos)
        self._campanas = campanas
        self._almacen = almacen
        self._uow = uow

    def ejecutar(
        self, owner_id: IdPublico, campana_id: IdPublico, nombre: str, contenido: bytes
    ) -> DetalleCampana:
        archivo = ArchivoCampana.crear(nombre, contenido)
        self._campanas.obtener(owner_id, campana_id).exigir_borrador()
        referencia = self._almacen.guardar(archivo, owner_id, campana_id)
        with self._uow:
            campana = self._campanas.bloquear(owner_id, campana_id)
            campana.adjuntar(referencia)
            self._campanas.guardar(campana)
        return self._detalle(campana)


class DescargarAdjunto:
    def __init__(self, campanas: IRepoCampanas, almacen: IAlmacenArchivos) -> None:
        self._campanas = campanas
        self._almacen = almacen

    def ejecutar(self, owner_id: IdPublico, campana_id: IdPublico) -> ArchivoDescargado:
        campana = self._campanas.obtener(owner_id, campana_id)
        archivo = self._almacen.obtener(campana.adjunto) if campana.adjunto else None
        if archivo is None:
            raise RecursoNoEncontrado("La campaña no tiene adjunto.")
        return archivo
