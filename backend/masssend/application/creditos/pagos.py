"""Iniciar y confirmar compras de creditos."""

from dataclasses import dataclass

from masssend.application.creditos.puertos import IConsultasCreditos, ISelectorPasarela
from masssend.application.shared.puertos import IGeneradorIds, IUnidadDeTrabajo
from masssend.domain.creditos.compra import Compra
from masssend.domain.creditos.repositorios import IRepoBilleteras, IRepoCompras
from masssend.domain.shared.dinero import Dinero
from masssend.domain.shared.errores import RecursoNoEncontrado
from masssend.domain.shared.identificadores import IdPublico


@dataclass(frozen=True, slots=True)
class CompraIniciada:
    compra_id: IdPublico
    pasarela: str
    referencia: str
    url_pago: str | None
    monto: Dinero
    creditos: int


@dataclass(frozen=True, slots=True)
class CompraConfirmada:
    estado: str
    creditos: int
    ya_procesada: bool


class IniciarCompra:
    def __init__(
        self,
        consultas: IConsultasCreditos,
        pasarelas: ISelectorPasarela,
        compras: IRepoCompras,
        ids: IGeneradorIds,
        uow: IUnidadDeTrabajo,
    ) -> None:
        self._consultas = consultas
        self._pasarelas = pasarelas
        self._compras = compras
        self._ids = ids
        self._uow = uow

    def ejecutar(self, dueno_id: IdPublico, paquete_id: int, nombre: str) -> CompraIniciada:
        paquete = self._consultas.paquete_activo(paquete_id)
        if paquete is None:
            raise RecursoNoEncontrado("El paquete no existe o ya no está disponible.")
        pasarela = self._pasarelas.pasarela(nombre)
        compra_id = self._ids.nuevo()
        cobro = pasarela.iniciar(paquete, str(compra_id))
        compra = Compra(
            compra_id,
            dueno_id,
            paquete.id,
            pasarela.nombre,
            cobro.referencia,
            paquete.precio,
            paquete.creditos,
        )
        with self._uow:
            self._compras.agregar(compra)
            self._compras.guardar(compra, cobro.respuesta)
        return CompraIniciada(
            compra_id,
            pasarela.nombre,
            cobro.referencia,
            cobro.url_pago,
            compra.monto,
            compra.creditos,
        )


class ConfirmarCompra:
    def __init__(
        self,
        pasarelas: ISelectorPasarela,
        compras: IRepoCompras,
        billeteras: IRepoBilleteras,
        uow: IUnidadDeTrabajo,
    ) -> None:
        self._pasarelas = pasarelas
        self._compras = compras
        self._billeteras = billeteras
        self._uow = uow

    def ejecutar(
        self, dueno_id: IdPublico, compra_id: IdPublico, datos: dict[str, object]
    ) -> CompraConfirmada:
        compra = self._compras.obtener(compra_id)
        if compra.dueno_id != dueno_id:
            raise RecursoNoEncontrado("La compra no existe.")
        if compra.aprobada:
            return CompraConfirmada(compra.estado.value, compra.creditos, True)

        # La pasarela se consulta sin bloqueos; la decision se toma con la fila retenida.
        cobro = self._pasarelas.pasarela(compra.pasarela).confirmar(compra.referencia, datos)
        monto_correcto = cobro.monto is None or cobro.monto == compra.monto

        with self._uow:
            billetera = self._billeteras.bloquear(dueno_id)
            actual = self._compras.bloquear(compra_id)
            if actual.aprobada:
                return CompraConfirmada(actual.estado.value, actual.creditos, True)
            if not (cobro.aprobado and monto_correcto):
                actual.rechazar()
                self._compras.guardar(actual, cobro.respuesta)
                return CompraConfirmada(actual.estado.value, 0, False)
            actual.aprobar()
            billetera.acreditar(actual.creditos)
            self._compras.guardar(actual, cobro.respuesta)
            self._billeteras.guardar(billetera)
            return CompraConfirmada(actual.estado.value, actual.creditos, False)
