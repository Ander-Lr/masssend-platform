"""Catálogo público de paquetes de créditos (no requiere sesión activa
específica, solo estar logueado, igual que el resto de la app)."""
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from ..repositories import transaction_repository
from ..utils.auth import get_authenticated_user


def _serialize_pack(pack):
    return {
        "id": pack.id,
        "name": pack.name,
        "credits": pack.credits,
        "price_usd": str(pack.price_usd),
    }


@csrf_exempt
@require_http_methods(["GET"])
def list_packs(request):
    user = get_authenticated_user(request)
    if not user:
        return JsonResponse({"success": False, "error": "No autenticado"}, status=401)

    packs = transaction_repository.get_active_packs()
    return JsonResponse({"success": True, "packs": [_serialize_pack(p) for p in packs]})
