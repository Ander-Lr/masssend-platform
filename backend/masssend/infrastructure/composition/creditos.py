"""Contenedor del modulo de creditos."""

from django.conf import settings

from masssend.application.creditos.consultas import (
    ConsultarSaldo,
    ListarMovimientos,
    ListarPaquetes,
)
from masssend.application.creditos.pagos import ConfirmarCompra, IniciarCompra
from masssend.application.creditos.reservas import (
    ConsumirCredito,
    LiberarReserva,
    ReservarCreditos,
)
from masssend.application.envio.puertos import IReservaCreditos
from masssend.infrastructure.adapters.creditos.reserva_envio import ReservaCreditosLocal
from masssend.infrastructure.adapters.pagos.selector import SelectorPasarelas
from masssend.infrastructure.composition.root import contenedor as raiz
from masssend.infrastructure.persistence.creditos.consultas import ConsultasCreditosDjango
from masssend.infrastructure.persistence.creditos.repositorios import (
    RepoBilleterasDjango,
    RepoComprasDjango,
    RepoReservasDjango,
)


def pasarelas_reales() -> frozenset[str]:
    """auto sigue a PASARELA_PAGO_FAKE; real o falsa lo fijan por pasarela."""
    por_defecto = "falsa" if settings.PASARELA_PAGO_FAKE else "real"
    modos = {"PAYPAL": settings.PASARELA_PAYPAL, "PAYPHONE": settings.PASARELA_PAYPHONE}
    elegidos = {nombre: por_defecto if modo == "auto" else modo for nombre, modo in modos.items()}
    return frozenset(nombre for nombre, modo in elegidos.items() if modo == "real")


class ContenedorCreditos:
    def consultar_saldo(self) -> ConsultarSaldo:
        return ConsultarSaldo(RepoBilleterasDjango())

    def listar_paquetes(self) -> ListarPaquetes:
        return ListarPaquetes(ConsultasCreditosDjango())

    def listar_movimientos(self) -> ListarMovimientos:
        return ListarMovimientos(ConsultasCreditosDjango())

    def iniciar_compra(self) -> IniciarCompra:
        return IniciarCompra(
            ConsultasCreditosDjango(),
            SelectorPasarelas(pasarelas_reales()),
            RepoComprasDjango(),
            raiz.generador_ids(),
            raiz.unidad_de_trabajo(),
        )

    def confirmar_compra(self) -> ConfirmarCompra:
        return ConfirmarCompra(
            SelectorPasarelas(pasarelas_reales()),
            RepoComprasDjango(),
            RepoBilleterasDjango(),
            raiz.unidad_de_trabajo(),
        )

    def reserva_creditos(self) -> IReservaCreditos:
        """El modulo de envio obtiene aqui el adaptador real."""
        billeteras = RepoBilleterasDjango()
        reservas = RepoReservasDjango()
        return ReservaCreditosLocal(
            ReservarCreditos(
                billeteras, reservas, raiz.generador_ids(), raiz.unidad_de_trabajo()
            ),
            ConsumirCredito(billeteras, reservas, raiz.unidad_de_trabajo()),
            LiberarReserva(billeteras, reservas, raiz.unidad_de_trabajo()),
        )


contenedor_creditos = ContenedorCreditos()
