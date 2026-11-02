"""Contenedor del modulo de creditos."""

from masssend.application.creditos.consultas import (
    ConsultarSaldo,
    ListarMovimientos,
    ListarPaquetes,
)
from masssend.application.creditos.reservas import (
    ConsumirCredito,
    LiberarReserva,
    ReservarCreditos,
)
from masssend.application.envio.puertos import IReservaCreditos
from masssend.infrastructure.adapters.creditos.reserva_envio import ReservaCreditosLocal
from masssend.infrastructure.composition.root import contenedor as raiz
from masssend.infrastructure.persistence.creditos.consultas import ConsultasCreditosDjango
from masssend.infrastructure.persistence.creditos.repositorios import (
    RepoBilleterasDjango,
    RepoReservasDjango,
)


class ContenedorCreditos:
    def consultar_saldo(self) -> ConsultarSaldo:
        return ConsultarSaldo(RepoBilleterasDjango())

    def listar_paquetes(self) -> ListarPaquetes:
        return ListarPaquetes(ConsultasCreditosDjango())

    def listar_movimientos(self) -> ListarMovimientos:
        return ListarMovimientos(ConsultasCreditosDjango())

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
