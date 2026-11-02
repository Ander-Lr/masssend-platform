from dataclasses import dataclass, field

import pytest

from masssend.application.creditos.pagos import ConfirmarCompra, IniciarCompra
from masssend.application.creditos.puertos import (
    IConsultasCreditos,
    IPasarelaPago,
    ISelectorPasarela,
    Paquete,
)
from masssend.domain.creditos.compra import EstadoCompra
from masssend.domain.creditos.repositorios import IRepoCompras
from masssend.domain.shared.dinero import Dinero
from masssend.domain.shared.errores import DatosInvalidos, RecursoNoEncontrado
from masssend.domain.shared.identificadores import IdPublico
from tests.fakes.creditos import RepoBilleterasMemoria, RepoReservasMemoria
from tests.fakes.ids import GeneradorIdsSecuencial
from tests.fakes.pagos import (
    ConsultasFalsas,
    PasarelaFalsa,
    RepoComprasMemoria,
    SelectorFalso,
)
from tests.fakes.unidad_de_trabajo import UnidadDeTrabajoFalsa

PAQUETE = Paquete(1, "Base", 100, Dinero(500))


@dataclass
class Entorno:
    ids: GeneradorIdsSecuencial = field(default_factory=GeneradorIdsSecuencial)
    uow: UnidadDeTrabajoFalsa = field(default_factory=UnidadDeTrabajoFalsa)
    pasarela: PasarelaFalsa = field(default_factory=PasarelaFalsa)
    compras: RepoComprasMemoria = field(default_factory=RepoComprasMemoria)

    def __post_init__(self) -> None:
        self.billeteras = RepoBilleterasMemoria(RepoReservasMemoria())
        self.ana = self.ids.nuevo()
        self.iniciar = IniciarCompra(
            ConsultasFalsas([PAQUETE]),
            SelectorFalso(self.pasarela),
            self.compras,
            self.ids,
            self.uow,
        )
        self.confirmar = ConfirmarCompra(
            SelectorFalso(self.pasarela), self.compras, self.billeteras, self.uow
        )

    def compra(self) -> IdPublico:
        return self.iniciar.ejecutar(self.ana, 1, "paypal").compra_id

    def saldo(self) -> int:
        return self.billeteras.obtener(self.ana).saldo


def test_los_fakes_cumplen_los_puertos() -> None:
    e = Entorno()
    consultas: IConsultasCreditos = ConsultasFalsas([])
    pasarela: IPasarelaPago = e.pasarela
    selector: ISelectorPasarela = SelectorFalso(pasarela)
    compras: IRepoCompras = e.compras
    assert all((consultas, selector, compras))


def test_el_servidor_fija_precio_y_creditos() -> None:
    e = Entorno()
    iniciada = e.iniciar.ejecutar(e.ana, 1, "paypal")
    assert (iniciada.monto, iniciada.creditos) == (Dinero(500), 100)
    assert iniciada.url_pago == "https://pago.prueba"
    assert e.compras.obtener(iniciada.compra_id).estado is EstadoCompra.PENDIENTE


def test_un_paquete_inexistente_no_se_compra() -> None:
    e = Entorno()
    with pytest.raises(RecursoNoEncontrado):
        e.iniciar.ejecutar(e.ana, 99, "paypal")


def test_una_pasarela_inexistente_se_rechaza() -> None:
    e = Entorno()
    with pytest.raises(DatosInvalidos):
        e.iniciar.ejecutar(e.ana, 1, "bitcoin")


def test_confirmar_acredita() -> None:
    e = Entorno()
    resultado = e.confirmar.ejecutar(e.ana, e.compra(), {})
    assert (resultado.estado, resultado.creditos, resultado.ya_procesada) == (
        "aprobada",
        100,
        False,
    )
    assert e.saldo() == 100


def test_confirmar_de_nuevo_no_acredita_ni_consulta_la_pasarela() -> None:
    e = Entorno()
    compra = e.compra()
    for _ in range(10):
        resultado = e.confirmar.ejecutar(e.ana, compra, {})
    assert resultado.ya_procesada
    assert e.saldo() == 100
    assert e.pasarela.confirmaciones == 1


def test_una_compra_ajena_no_se_encuentra() -> None:
    e = Entorno()
    with pytest.raises(RecursoNoEncontrado):
        e.confirmar.ejecutar(e.ids.nuevo(), e.compra(), {})
    assert e.saldo() == 0


def test_un_pago_rechazado_no_acredita() -> None:
    e = Entorno()
    e.pasarela.aprueba = False
    resultado = e.confirmar.ejecutar(e.ana, e.compra(), {})
    assert (resultado.estado, resultado.creditos) == ("rechazada", 0)
    assert e.saldo() == 0


def test_un_pago_rechazado_puede_aprobarse_despues() -> None:
    e = Entorno()
    compra = e.compra()
    e.pasarela.aprueba = False
    e.confirmar.ejecutar(e.ana, compra, {})
    e.pasarela.aprueba = True
    assert e.confirmar.ejecutar(e.ana, compra, {}).estado == "aprobada"
    assert e.saldo() == 100


def test_un_cobro_por_otro_monto_no_acredita() -> None:
    e = Entorno()
    e.pasarela.monto_cobrado = Dinero(1)
    assert e.confirmar.ejecutar(e.ana, e.compra(), {}).estado == "rechazada"
    assert e.saldo() == 0


def test_un_cobro_por_el_monto_exacto_acredita() -> None:
    e = Entorno()
    e.pasarela.monto_cobrado = Dinero(500)
    assert e.confirmar.ejecutar(e.ana, e.compra(), {}).estado == "aprobada"


def test_una_compra_aprobada_no_vuelve_a_rechazarse() -> None:
    e = Entorno()
    compra_id = e.compra()
    e.confirmar.ejecutar(e.ana, compra_id, {})
    compra = e.compras.obtener(compra_id)
    compra.rechazar()
    assert compra.aprobada
