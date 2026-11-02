"""
Orquesta el checkout: elige la pasarela (factory simple por nombre,
así agregar una pasarela nueva no toca views ni el resto de services),
crea el PaymentTransaction PENDING, y al confirmar acredita los
créditos a la wallet del usuario de forma atómica.
"""
from typing import Optional

from django.db import transaction as db_transaction

from .gateways.paypal_gateway import PayPalGateway
from .gateways.payphone_gateway import PayPhoneGateway
from .wallet_service import add_credits
from ..repositories import transaction_repository
from ..models import PaymentTransaction
from ..utils.errors import AppError

_GATEWAYS = {
    PaymentTransaction.PROVIDER_PAYPAL: PayPalGateway(),
    PaymentTransaction.PROVIDER_PAYPHONE: PayPhoneGateway(),
}


def _get_gateway(provider: str):
    gateway = _GATEWAYS.get((provider or "").upper())
    if gateway is None:
        raise AppError(f"Pasarela de pago no soportada: {provider}", 400)
    return gateway


def start_checkout(*, user, pack_id: int, provider: str):
    pack = transaction_repository.get_pack_or_none(pack_id)
    if pack is None:
        raise AppError("El paquete de créditos seleccionado no existe o ya no está disponible.", 404)

    gateway = _get_gateway(provider)
    reference_hint = f"user{user.id}-pack{pack.id}"

    result = gateway.create_payment(pack=pack, reference_hint=reference_hint)

    transaction_obj = transaction_repository.create_pending_transaction(
        user=user,
        pack=pack,
        provider=gateway.name,
        provider_reference=result["provider_reference"],
        raw_response=result.get("raw", {}),
    )

    return {
        "transaction_id": str(transaction_obj.id),
        "provider": gateway.name,
        "provider_reference": result["provider_reference"],
        "redirect_url": result.get("redirect_url"),
    }


def confirm_checkout(*, provider: str, provider_reference: str, extra: Optional[dict] = None):
    gateway = _get_gateway(provider)

    transaction_obj = transaction_repository.find_by_reference(
        provider=gateway.name, provider_reference=provider_reference,
    )
    if transaction_obj is None:
        raise AppError("No se encontró la transacción a confirmar.", 404)

    if transaction_obj.status == PaymentTransaction.STATUS_APPROVED:
        # Ya se había confirmado antes (doble click / doble callback):
        # no volver a acreditar créditos, solo responder OK.
        return {"approved": True, "already_processed": True, "credits": transaction_obj.credits}

    result = gateway.confirm_payment(provider_reference=provider_reference, extra=extra or {})

    if not result.get("approved"):
        transaction_repository.mark_failed(transaction_obj, result.get("raw"))
        return {"approved": False, "already_processed": False}

    with db_transaction.atomic():
        transaction_repository.mark_approved(transaction_obj, result.get("raw"))
        add_credits(transaction_obj.user, transaction_obj.credits)

    return {"approved": True, "already_processed": False, "credits": transaction_obj.credits}
