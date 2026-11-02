from typing import Protocol

from masssend.domain.identidad.cuenta import Cuenta
from masssend.domain.identidad.desafio import Desafio, Proposito
from masssend.domain.shared.identificadores import IdPublico


class IRepoCuentas(Protocol):
    def buscar_por_correo(self, correo: str) -> Cuenta | None: ...

    def bloquear_por_correo(self, correo: str) -> Cuenta | None:
        """Como buscar_por_correo, pero retiene la fila hasta confirmar."""
        ...

    def obtener(self, cuenta_id: IdPublico) -> Cuenta:
        """Lanza RecursoNoEncontrado si no existe."""
        ...

    def bloquear(self, cuenta_id: IdPublico) -> Cuenta: ...

    def guardar(self, cuenta: Cuenta) -> None: ...


class IRepoDesafios(Protocol):
    def agregar(self, desafio: Desafio) -> None: ...

    def bloquear_por_hash(self, hash_token: str, proposito: Proposito) -> Desafio | None: ...

    def guardar(self, desafio: Desafio) -> None: ...

    def anular_pendientes(self, cuenta_id: IdPublico, proposito: Proposito) -> None: ...
