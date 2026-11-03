from collections.abc import Collection, Sequence
from dataclasses import dataclass
from typing import Protocol

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

    def listar(
        self, owner_id: IdPublico, filtro: FiltroContactos, peticion: PeticionPagina
    ) -> Pagina[Contacto]: ...
