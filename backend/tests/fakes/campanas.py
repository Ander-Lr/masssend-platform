from collections.abc import Collection, Iterable, Sequence
from dataclasses import replace
from typing import Protocol, TypeVar

from masssend.application.campanas.puertos import ArchivoDescargado
from masssend.domain.campanas.archivo import ArchivoCampana
from masssend.domain.campanas.campana import Campana
from masssend.domain.campanas.contacto import Contacto
from masssend.domain.campanas.repositorios import FiltroCampanas, FiltroContactos
from masssend.domain.campanas.telefono import Telefono
from masssend.domain.shared.errores import (
    EstadoInvalido,
    RecursoNoEncontrado,
    ServicioNoDisponible,
)
from masssend.domain.shared.identificadores import IdPublico
from masssend.domain.shared.paginacion import Cursor, Pagina, PeticionPagina


class _ConId(Protocol):
    @property
    def id(self) -> IdPublico: ...


T = TypeVar("T", bound=_ConId)


def _copia(contacto: Contacto) -> Contacto:
    return replace(contacto, datos=dict(contacto.datos))


def _paginar(filas: Iterable[T], peticion: PeticionPagina) -> Pagina[T]:
    """Del id mas nuevo al mas antiguo, como los repositorios reales."""
    ordenadas = sorted(filas, key=lambda f: str(f.id), reverse=True)
    if peticion.cursor is not None:
        ultimo = peticion.cursor.valores[0]
        ordenadas = [f for f in ordenadas if str(f.id) < ultimo]
    return Pagina.desde_filas(
        ordenadas[: peticion.limite + 1], peticion, lambda f: Cursor((str(f.id),))
    )


class RepoContactosMemoria:
    """Guarda copias, como una base real: cambiar un objeto no lo persiste."""

    def __init__(self) -> None:
        self.contactos: dict[IdPublico, Contacto] = {}
        self._por_telefono: dict[tuple[IdPublico, Telefono], IdPublico] = {}
        self.busquedas = 0
        self.guardados_en_bloque = 0

    def obtener(self, owner_id: IdPublico, contacto_id: IdPublico) -> Contacto:
        contacto = self.contactos.get(contacto_id)
        if contacto is None or not contacto.pertenece_a(owner_id):
            raise RecursoNoEncontrado("El contacto no existe.")
        return _copia(contacto)

    def buscar_por_telefonos(
        self, owner_id: IdPublico, telefonos: Collection[Telefono]
    ) -> dict[Telefono, Contacto]:
        self.busquedas += 1
        encontrados: dict[Telefono, Contacto] = {}
        for telefono in telefonos:
            contacto_id = self._por_telefono.get((owner_id, telefono))
            if contacto_id is not None:
                encontrados[telefono] = _copia(self.contactos[contacto_id])
        return encontrados

    def guardar(self, contacto: Contacto) -> None:
        clave = (contacto.owner_id, contacto.telefono)
        if self._por_telefono.get(clave, contacto.id) != contacto.id:
            raise EstadoInvalido("El dueño ya tiene ese teléfono.")
        self._por_telefono[clave] = contacto.id
        self.contactos[contacto.id] = _copia(contacto)

    def guardar_varios(self, contactos: Sequence[Contacto]) -> None:
        self.guardados_en_bloque += 1
        for contacto in contactos:
            self.guardar(contacto)

    def eliminar(self, owner_id: IdPublico, contacto_id: IdPublico) -> None:
        contacto = self.obtener(owner_id, contacto_id)
        del self._por_telefono[(owner_id, contacto.telefono)]
        del self.contactos[contacto_id]

    def eliminar_varios(self, owner_id: IdPublico, contacto_ids: Collection[IdPublico]) -> int:
        borrados = 0
        for contacto_id in contacto_ids:
            contacto = self.contactos.get(contacto_id)
            if contacto is not None and contacto.pertenece_a(owner_id):
                self.eliminar(owner_id, contacto_id)
                borrados += 1
        return borrados

    def etiquetas(self, owner_id: IdPublico) -> list[str]:
        return sorted(
            {e for c in self.contactos.values() if c.pertenece_a(owner_id) for e in c.etiquetas}
        )

    def listar(
        self, owner_id: IdPublico, filtro: FiltroContactos, peticion: PeticionPagina
    ) -> Pagina[Contacto]:
        texto = (filtro.texto or "").lower()
        return _paginar(
            (
                _copia(c)
                for c in self.contactos.values()
                if c.pertenece_a(owner_id)
                and (not texto or texto in c.nombre.lower() or texto in c.telefono.numero)
                and (filtro.etiqueta is None or filtro.etiqueta in c.etiquetas)
            ),
            peticion,
        )

    def _destinatarios(self, owner_id: IdPublico, etiquetas: Collection[str]) -> list[Contacto]:
        return [
            _copia(c)
            for c in self.contactos.values()
            if c.pertenece_a(owner_id) and c.puede_recibir and c.tiene_alguna_etiqueta(etiquetas)
        ]

    def dar_de_baja_en_todas_las_libretas(self, telefono: Telefono) -> int:
        cambiados = 0
        for contacto in self.contactos.values():
            if contacto.telefono == telefono and contacto.puede_recibir:
                contacto.dar_de_baja()
                cambiados += 1
        return cambiados

    def contar_destinatarios(self, owner_id: IdPublico, etiquetas: Collection[str]) -> int:
        return len(self._destinatarios(owner_id, etiquetas))

    def destinatarios(
        self, owner_id: IdPublico, etiquetas: Collection[str], peticion: PeticionPagina
    ) -> Pagina[Contacto]:
        return _paginar(self._destinatarios(owner_id, etiquetas), peticion)


class RepoCampanasMemoria:
    def __init__(self) -> None:
        self.campanas: dict[IdPublico, Campana] = {}
        self.bloqueos = 0

    def obtener(self, owner_id: IdPublico, campana_id: IdPublico) -> Campana:
        campana = self.campanas.get(campana_id)
        if campana is None or not campana.pertenece_a(owner_id):
            raise RecursoNoEncontrado("La campaña no existe.")
        return replace(campana)

    def bloquear(self, owner_id: IdPublico, campana_id: IdPublico) -> Campana:
        self.bloqueos += 1
        return self.obtener(owner_id, campana_id)

    def guardar(self, campana: Campana) -> None:
        self.campanas[campana.id] = replace(campana)

    def eliminar(self, owner_id: IdPublico, campana_id: IdPublico) -> None:
        self.obtener(owner_id, campana_id)
        del self.campanas[campana_id]

    def listar(
        self, owner_id: IdPublico, filtro: FiltroCampanas, peticion: PeticionPagina
    ) -> Pagina[Campana]:
        return _paginar(
            (
                replace(c)
                for c in self.campanas.values()
                if c.pertenece_a(owner_id) and (filtro.estado is None or c.estado is filtro.estado)
            ),
            peticion,
        )


class AlmacenArchivosMemoria:
    """Guarda en un diccionario. disponible=False simula un almacen caido."""

    def __init__(self) -> None:
        self.archivos: dict[str, ArchivoCampana] = {}
        self.disponible = True

    def guardar(self, archivo: ArchivoCampana, owner_id: IdPublico, campana_id: IdPublico) -> str:
        if not self.disponible:
            raise ServicioNoDisponible("El almacén de archivos no responde.")
        referencia = f"memoria://{campana_id}/{len(self.archivos) + 1}/{archivo.nombre}"
        self.archivos[referencia] = archivo
        return referencia

    def obtener(self, referencia: str) -> ArchivoDescargado | None:
        if not self.disponible:
            raise ServicioNoDisponible("El almacén de archivos no responde.")
        archivo = self.archivos.get(referencia)
        if archivo is None:
            return None
        return ArchivoDescargado(archivo.nombre, archivo.tipo, archivo.contenido)
