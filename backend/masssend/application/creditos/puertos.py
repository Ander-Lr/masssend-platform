from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from masssend.domain.shared.dinero import Dinero
from masssend.domain.shared.identificadores import IdPublico
from masssend.domain.shared.paginacion import Pagina, PeticionPagina


@dataclass(frozen=True, slots=True)
class Paquete:
    id: int
    nombre: str
    creditos: int
    precio: Dinero


@dataclass(frozen=True, slots=True)
class Movimiento:
    tipo: str
    creditos: int
    fecha: datetime
    detalle: str


@dataclass(frozen=True, slots=True)
class CobroIniciado:
    referencia: str
    url_pago: str | None
    respuesta: dict[str, object]


@dataclass(frozen=True, slots=True)
class CobroConfirmado:
    """monto es None si la pasarela no informa lo que cobro."""

    aprobado: bool
    monto: Dinero | None
    respuesta: dict[str, object]


class IPasarelaPago(Protocol):
    nombre: str

    def iniciar(self, paquete: Paquete, referencia: str) -> CobroIniciado:
        """Lanza ServicioNoDisponible si la pasarela no responde."""
        ...

    def confirmar(self, referencia: str, datos: dict[str, object]) -> CobroConfirmado:
        """Consulta a la pasarela: nunca se confia en lo que diga el cliente."""
        ...


class ISelectorPasarela(Protocol):
    def pasarela(self, nombre: str) -> IPasarelaPago:
        """Lanza DatosInvalidos si no existe."""
        ...


class IConsultasCreditos(Protocol):
    def paquetes_activos(self) -> list[Paquete]: ...

    def paquete_activo(self, paquete_id: int) -> Paquete | None: ...

    def movimientos(
        self, dueno_id: IdPublico, peticion: PeticionPagina
    ) -> Pagina[Movimiento]: ...
