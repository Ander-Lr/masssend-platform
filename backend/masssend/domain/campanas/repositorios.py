from collections.abc import Collection, Sequence
from dataclasses import dataclass
from typing import Protocol

from masssend.domain.campanas.campana import Campana, EstadoCampana
from masssend.domain.campanas.contacto import Contacto
from masssend.domain.campanas.telefono import Telefono
from masssend.domain.shared.identificadores import IdPublico
from masssend.domain.shared.paginacion import Pagina, PeticionPagina


@dataclass(frozen=True, slots=True)
class FiltroContactos:
    """texto busca en nombre y telefono; etiqueta exige esa etiqueta exacta."""

    texto: str | None = None
    etiqueta: str | None = None


class IRepoContactos(Protocol):
    """Toda operacion recibe owner_id: nunca se ve ni se toca un contacto ajeno."""

    def obtener(self, owner_id: IdPublico, contacto_id: IdPublico) -> Contacto:
        """Lanza RecursoNoEncontrado si no existe o es de otro dueno."""
        ...

    def buscar_por_telefonos(
        self, owner_id: IdPublico, telefonos: Collection[Telefono]
    ) -> dict[Telefono, Contacto]:
        """Una sola consulta para todo el lote; solo devuelve los que existen."""
        ...

    def guardar(self, contacto: Contacto) -> None:
        """Crea o actualiza. Respeta la unicidad por dueno y telefono."""
        ...

    def guardar_varios(self, contactos: Sequence[Contacto]) -> None:
        """Como guardar, pero en bloque para la importacion."""
        ...

    def eliminar(self, owner_id: IdPublico, contacto_id: IdPublico) -> None:
        """Lanza RecursoNoEncontrado si no existe o es de otro dueno."""
        ...

    def eliminar_varios(self, owner_id: IdPublico, contacto_ids: Collection[IdPublico]) -> int:
        """Borra solo los propios e ignora el resto. Devuelve cuantos borro."""
        ...

    def listar(
        self, owner_id: IdPublico, filtro: FiltroContactos, peticion: PeticionPagina
    ) -> Pagina[Contacto]:
        """Del mas nuevo al mas antiguo, por cursor."""
        ...

    def etiquetas(self, owner_id: IdPublico) -> list[str]:
        """Etiquetas distintas que usa el dueno, en orden alfabetico."""
        ...

    def dar_de_baja_en_todas_las_libretas(self, telefono: Telefono) -> int:
        """Operacion del sistema, no de un dueno: quien escribe BAJA al numero de la
        plataforma no quiere mensajes de nadie. Devuelve cuantos contactos cambiaron."""
        ...

    def contar_destinatarios(self, owner_id: IdPublico, etiquetas: Collection[str]) -> int:
        """Contactos que recibirian la campana. Ver destinatarios."""
        ...

    def destinatarios(
        self, owner_id: IdPublico, etiquetas: Collection[str], peticion: PeticionPagina
    ) -> Pagina[Contacto]:
        """Contactos del dueno que no se dieron de baja y tienen alguna de las
        etiquetas. Sin etiquetas, todos. Trasladado de destinatarios_campana."""
        ...


@dataclass(frozen=True, slots=True)
class FiltroCampanas:
    estado: EstadoCampana | None = None


class IRepoCampanas(Protocol):
    """Toda operacion recibe owner_id: una campana ajena no existe para el usuario."""

    def obtener(self, owner_id: IdPublico, campana_id: IdPublico) -> Campana:
        """Lanza RecursoNoEncontrado si no existe o es de otro dueno."""
        ...

    def bloquear(self, owner_id: IdPublico, campana_id: IdPublico) -> Campana:
        """Como obtener, pero retiene la fila hasta confirmar."""
        ...

    def guardar(self, campana: Campana) -> None: ...

    def eliminar(self, owner_id: IdPublico, campana_id: IdPublico) -> None:
        """Borra la campana con su progreso y sus mensajes."""
        ...

    def listar(
        self, owner_id: IdPublico, filtro: FiltroCampanas, peticion: PeticionPagina
    ) -> Pagina[Campana]:
        """De la mas nueva a la mas antigua, por cursor."""
        ...
