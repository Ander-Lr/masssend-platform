from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.utils import timezone

from billing.models import CreditSpend, CreditWallet, PaymentTransaction
from billing.repositories import wallet_repository
from masssend.domain.creditos.billetera import Billetera
from masssend.domain.creditos.compra import Compra, EstadoCompra
from masssend.domain.creditos.reserva import Reserva
from masssend.domain.shared.dinero import Dinero
from masssend.domain.shared.errores import RecursoNoEncontrado
from masssend.domain.shared.identificadores import IdPublico
from masssend.infrastructure.persistence.creditos.models import ConsumoCredito, ReservaCreditos
from masssend.infrastructure.persistence.identidad.models import CuentaIdentidad

Usuario = get_user_model()

ESTADOS = {
    PaymentTransaction.STATUS_PENDING: EstadoCompra.PENDIENTE,
    PaymentTransaction.STATUS_APPROVED: EstadoCompra.APROBADA,
    PaymentTransaction.STATUS_FAILED: EstadoCompra.RECHAZADA,
}
ESTADOS_DB = {estado: clave for clave, estado in ESTADOS.items()}


def usuario_de(dueno_id: IdPublico) -> int:
    usuario_id = (
        CuentaIdentidad.objects.filter(public_id=dueno_id)
        .values_list("usuario_id", flat=True)
        .first()
    )
    if usuario_id is None:
        raise RecursoNoEncontrado("La cuenta no existe.")
    return usuario_id


class RepoBilleterasDjango:
    def obtener(self, dueno_id: IdPublico) -> Billetera:
        usuario_id = usuario_de(dueno_id)
        # Reutiliza la regla actual: la primera vez entrega los creditos de bienvenida.
        billetera = wallet_repository.get_or_create_wallet(Usuario(pk=usuario_id))
        return self._a_billetera(dueno_id, usuario_id, billetera.balance)

    def bloquear(self, dueno_id: IdPublico) -> Billetera:
        usuario_id = usuario_de(dueno_id)
        wallet_repository.get_or_create_wallet(Usuario(pk=usuario_id))
        fila = CreditWallet.objects.select_for_update().get(user_id=usuario_id)
        return self._a_billetera(dueno_id, usuario_id, fila.balance)

    def guardar(self, billetera: Billetera) -> None:
        CreditWallet.objects.filter(user_id=usuario_de(billetera.dueno_id)).update(
            balance=billetera.saldo, updated_at=timezone.now()
        )

    @staticmethod
    def _a_billetera(dueno_id: IdPublico, usuario_id: int, saldo: int) -> Billetera:
        # Lo reservado se calcula: asi no puede desincronizarse de las reservas.
        reservado = ReservaCreditos.objects.filter(
            usuario_id=usuario_id, restante__gt=0
        ).aggregate(total=Sum("restante"))["total"]
        return Billetera(dueno_id, saldo, reservado or 0)


class RepoReservasDjango:
    def agregar(self, reserva: Reserva) -> None:
        ReservaCreditos.objects.create(
            id=reserva.id,
            usuario_id=usuario_de(reserva.dueno_id),
            campana_id=reserva.campana_id,
            cantidad=reserva.cantidad,
            restante=reserva.restante,
        )

    def obtener(self, reserva_id: IdPublico) -> Reserva:
        return self._a_reserva(ReservaCreditos.objects.all(), reserva_id)

    def bloquear(self, reserva_id: IdPublico) -> Reserva:
        return self._a_reserva(ReservaCreditos.objects.select_for_update(), reserva_id)

    def guardar(self, reserva: Reserva) -> None:
        ReservaCreditos.objects.filter(pk=reserva.id).update(restante=reserva.restante)

    def ya_consumido(self, reserva_id: IdPublico, mensaje_id: IdPublico) -> bool:
        return ConsumoCredito.objects.filter(
            reserva_id=reserva_id, mensaje_id=mensaje_id
        ).exists()

    def registrar_consumo(self, reserva: Reserva, mensaje_id: IdPublico) -> None:
        ConsumoCredito.objects.create(reserva_id=reserva.id, mensaje_id=mensaje_id)
        CreditSpend.objects.create(
            user_id=usuario_de(reserva.dueno_id),
            amount=1,
            reason=f"Campaña {reserva.campana_id}",
        )

    @staticmethod
    def _a_reserva(consulta, reserva_id: IdPublico) -> Reserva:  # type: ignore[no-untyped-def]
        fila = consulta.filter(pk=reserva_id).first()
        if fila is None:
            raise RecursoNoEncontrado("La reserva no existe.")
        dueno = CuentaIdentidad.objects.values_list("public_id", flat=True).get(
            usuario_id=fila.usuario_id
        )
        return Reserva(
            IdPublico(fila.id),
            IdPublico(dueno),
            IdPublico(fila.campana_id),
            fila.cantidad,
            fila.restante,
        )


class RepoComprasDjango:
    def agregar(self, compra: Compra) -> None:
        PaymentTransaction.objects.create(
            id=compra.id,
            user_id=usuario_de(compra.dueno_id),
            pack_id=compra.paquete_id,
            provider=compra.pasarela,
            provider_reference=compra.referencia,
            amount_usd=compra.monto.como_decimal(),
            credits=compra.creditos,
            status=ESTADOS_DB[compra.estado],
        )

    def obtener(self, compra_id: IdPublico) -> Compra:
        return self._a_compra(PaymentTransaction.objects.all(), compra_id)

    def bloquear(self, compra_id: IdPublico) -> Compra:
        return self._a_compra(PaymentTransaction.objects.select_for_update(), compra_id)

    def guardar(self, compra: Compra, respuesta: dict[str, object]) -> None:
        PaymentTransaction.objects.filter(pk=compra.id).update(
            status=ESTADOS_DB[compra.estado],
            raw_response=respuesta,
            updated_at=timezone.now(),
        )

    @staticmethod
    def _a_compra(consulta, compra_id: IdPublico) -> Compra:  # type: ignore[no-untyped-def]
        fila = consulta.filter(pk=compra_id).first()
        if fila is None:
            raise RecursoNoEncontrado("La compra no existe.")
        dueno = CuentaIdentidad.objects.values_list("public_id", flat=True).filter(
            usuario_id=fila.user_id
        ).first()
        if dueno is None:
            raise RecursoNoEncontrado("La compra no existe.")
        return Compra(
            IdPublico(fila.id),
            IdPublico(dueno),
            fila.pack_id,
            fila.provider,
            fila.provider_reference,
            Dinero.desde_decimal(fila.amount_usd),
            fila.credits,
            ESTADOS[fila.status],
        )
