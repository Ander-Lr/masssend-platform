from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from ..services import wallet_service
from ..utils.auth import get_authenticated_user


def _serialize_transaction(t):
    return {
        "id": str(t.id),
        "provider": t.provider,
        "status": t.status,
        "amount_usd": str(t.amount_usd),
        "credits": t.credits,
        "pack_name": t.pack.name if t.pack else None,
        "created_at": t.created_at.isoformat(),
    }


@csrf_exempt
@require_http_methods(["GET"])
def get_wallet(request):
    user = get_authenticated_user(request)
    if not user:
        return JsonResponse({"success": False, "error": "No autenticado"}, status=401)

    return JsonResponse({"success": True, "balance": wallet_service.get_balance(user)})


@csrf_exempt
@require_http_methods(["GET"])
def get_history(request):
    user = get_authenticated_user(request)
    if not user:
        return JsonResponse({"success": False, "error": "No autenticado"}, status=401)

    history = wallet_service.get_history(user)
    return JsonResponse({"success": True, "transactions": [_serialize_transaction(t) for t in history]})
