from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.utils import timezone

from billing.models import CreditSpend, CreditWallet
from billing.repositories import wallet_repository
from masssend.domain.creditos.billetera import Billetera
from masssend.domain.creditos.reserva import Reserva
from masssend.domain.shared.errores import RecursoNoEncontrado
from masssend.domain.shared.identificadores import IdPublico
from masssend.infrastructure.persistence.creditos.models import ConsumoCredito, ReservaCreditos
from masssend.infrastructure.persistence.identidad.models import CuentaIdentidad

Usuario = get_user_model()


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
