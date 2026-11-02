"""Acceso a datos de PaymentTransaction y CreditPack."""
from ..models import PaymentTransaction, CreditPack


def get_active_packs():
    return CreditPack.objects.filter(is_active=True)


def get_pack_or_none(pack_id):
    return CreditPack.objects.filter(pk=pack_id, is_active=True).first()


def create_pending_transaction(*, user, pack, provider, provider_reference, raw_response=None):
    return PaymentTransaction.objects.create(
        user=user,
        pack=pack,
        provider=provider,
        provider_reference=provider_reference,
        amount_usd=pack.price_usd,
        credits=pack.credits,
        status=PaymentTransaction.STATUS_PENDING,
        raw_response=raw_response or {},
    )


def find_by_reference(*, provider, provider_reference):
    return (
        PaymentTransaction.objects
        .filter(provider=provider, provider_reference=provider_reference)
        .order_by("-created_at")
        .first()
    )


def mark_approved(transaction_obj, raw_response=None):
    transaction_obj.status = PaymentTransaction.STATUS_APPROVED
    if raw_response is not None:
        transaction_obj.raw_response = raw_response
    transaction_obj.save(update_fields=["status", "raw_response", "updated_at"])
    return transaction_obj


def mark_failed(transaction_obj, raw_response=None):
    transaction_obj.status = PaymentTransaction.STATUS_FAILED
    if raw_response is not None:
        transaction_obj.raw_response = raw_response
    transaction_obj.save(update_fields=["status", "raw_response", "updated_at"])
    return transaction_obj


def list_transactions_for_user(user, limit=20):
    return (
        PaymentTransaction.objects
        .filter(user=user)
        .select_related("pack")
        .order_by("-created_at")[:limit]
    )
