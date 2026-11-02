"""Reglas de negocio de la billetera de créditos."""
from ..repositories import wallet_repository, transaction_repository
from ..utils.errors import AppError


def get_balance(user) -> int:
    return wallet_repository.get_balance(user)


def get_history(user):
    return transaction_repository.list_transactions_for_user(user)


def spend_credits(user, amount: int, *, reason: str = ""):
    """Descuenta `amount` créditos del usuario. Lanza AppError (402)
    si no alcanza el saldo. reason es informativo (queda en CreditSpend
    solo como campo de auditoría; ver TODO abajo)."""
    if amount <= 0:
        return wallet_repository.get_or_create_wallet(user)
    try:
        wallet = wallet_repository.deduct_credits(user, amount)
    except ValueError:
        raise AppError(
            f"Saldo insuficiente: necesitas {amount} créditos para esta campaña. "
            f"Recarga en la sección Créditos.",
            402,
        )
    return wallet


def add_credits(user, amount: int):
    return wallet_repository.add_credits(user, amount)
