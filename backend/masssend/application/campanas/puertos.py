"""Puertos del modulo de campanas."""

from dataclasses import dataclass
from typing import Protocol

from masssend.domain.campanas.archivo import ArchivoCampana
from masssend.domain.shared.identificadores import IdPublico


@dataclass(frozen=True, slots=True)
class ArchivoDescargado:
    nombre: str
    tipo: str
    contenido: bytes


class IAlmacenArchivos(Protocol):
    """Guarda los adjuntos fuera de la base. PocketBase en local, S3 en la nube."""

    def guardar(self, archivo: ArchivoCampana, owner_id: IdPublico, campana_id: IdPublico) -> str:
        """Devuelve la referencia que se guarda en la campana.

        Lanza ServicioNoDisponible si el almacen no responde.
        """
        ...

    def obtener(self, referencia: str) -> ArchivoDescargado | None:
        """None si la referencia no es de este almacen o el archivo ya no existe.

        Lanza ServicioNoDisponible si el almacen no responde.
        """
        ...
