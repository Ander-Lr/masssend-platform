"""
Acceso a datos de CreditWallet y CreditSpend. Todo cambio de saldo
pasa por acá con `select_for_update` para que dos requests
concurrentes (p.ej. dos campañas ejecutándose a la vez) no puedan
dejar el saldo en un estado inconsistente.

Regalo de bienvenida: la primera vez que se crea la billetera de un
usuario (la primera vez que toca cualquier endpoint de créditos) se le
da `settings.FREE_SIGNUP_CREDITS` créditos gratis, para que pueda
probar el sistema antes de decidir pagar por más.
"""
from django.conf import settings
from django.db import transaction

from ..models import CreditWallet, CreditSpend


def _wallet_defaults() -> dict:
    return {"balance": getattr(settings, "FREE_SIGNUP_CREDITS", 0)}


def get_or_create_wallet(user) -> CreditWallet:
    wallet, _ = CreditWallet.objects.get_or_create(user=user, defaults=_wallet_defaults())
    return wallet


def get_balance(user) -> int:
    return get_or_create_wallet(user).balance


@transaction.atomic
def add_credits(user, amount: int) -> CreditWallet:
    wallet, _ = CreditWallet.objects.select_for_update().get_or_create(
        user=user, defaults=_wallet_defaults(),
    )
    wallet.balance = wallet.balance + amount
    wallet.save(update_fields=["balance", "updated_at"])
    return wallet


@transaction.atomic
def deduct_credits(user, amount: int) -> CreditWallet:
    """Descuenta créditos. Lanza ValueError si no alcanza el saldo
    (el llamador -wallet_service- lo traduce a AppError)."""
    wallet, _ = CreditWallet.objects.select_for_update().get_or_create(
        user=user, defaults=_wallet_defaults(),
    )
    if wallet.balance < amount:
        raise ValueError("insufficient_balance")
    wallet.balance = wallet.balance - amount
    wallet.save(update_fields=["balance", "updated_at"])
    CreditSpend.objects.create(user=user, amount=amount)
    return wallet
