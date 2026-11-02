from masssend.application.creditos.puertos import (
    CobroConfirmado,
    CobroIniciado,
    IPasarelaPago,
    Movimiento,
    Paquete,
)
from masssend.domain.creditos.compra import Compra
from masssend.domain.shared.dinero import Dinero
from masssend.domain.shared.errores import DatosInvalidos, RecursoNoEncontrado
from masssend.domain.shared.identificadores import IdPublico
from masssend.domain.shared.paginacion import Pagina, PeticionPagina


class PasarelaFalsa:
    def __init__(self, nombre: str = "PAYPAL") -> None:
        self.nombre = nombre
        self.aprueba = True
        self.monto_cobrado: Dinero | None = None
        self.confirmaciones = 0

    def iniciar(self, paquete: Paquete, referencia: str) -> CobroIniciado:
        return CobroIniciado(f"ref-{referencia}", "https://pago.prueba", {"creada": True})

    def confirmar(self, referencia: str, datos: dict[str, object]) -> CobroConfirmado:
        self.confirmaciones += 1
        return CobroConfirmado(self.aprueba, self.monto_cobrado, {"estado": "ok"})


class SelectorFalso:
    def __init__(self, pasarela: IPasarelaPago) -> None:
        self._pasarela = pasarela

    def pasarela(self, nombre: str) -> IPasarelaPago:
        if nombre.upper() != self._pasarela.nombre:
            raise DatosInvalidos("La pasarela no existe.", "pasarela")
        return self._pasarela


class RepoComprasMemoria:
    def __init__(self) -> None:
        self.compras: dict[IdPublico, Compra] = {}

    def agregar(self, compra: Compra) -> None:
        self.compras[compra.id] = compra

    def obtener(self, compra_id: IdPublico) -> Compra:
        if compra_id not in self.compras:
            raise RecursoNoEncontrado("La compra no existe.")
        return self.compras[compra_id]

    def bloquear(self, compra_id: IdPublico) -> Compra:
        return self.obtener(compra_id)

    def guardar(self, compra: Compra, respuesta: dict[str, object]) -> None:
        self.compras[compra.id] = compra


class ConsultasFalsas:
    def __init__(self, paquetes: list[Paquete]) -> None:
        self._paquetes = paquetes

    def paquetes_activos(self) -> list[Paquete]:
        return self._paquetes

    def paquete_activo(self, paquete_id: int) -> Paquete | None:
        return next((p for p in self._paquetes if p.id == paquete_id), None)

    def movimientos(
        self, dueno_id: IdPublico, peticion: PeticionPagina
    ) -> Pagina[Movimiento]:
        return Pagina(())
