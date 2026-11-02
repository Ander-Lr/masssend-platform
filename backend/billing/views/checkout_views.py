"""
Vistas de checkout. Django views planas (JsonResponse) igual que
mass_sender, no DRF: así evitamos el choque CSRF/SessionAuthentication
que ya tuvimos que resolver en email_auth para usuarios logueados por
sesión (Google / login clásico), sin duplicar esa configuración acá.
"""
import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from ..services import checkout_service
from ..utils.auth import get_authenticated_user
from ..utils.errors import AppError


@csrf_exempt
@require_http_methods(["POST"])
def start_checkout(request):
    user = get_authenticated_user(request)
    if not user:
        return JsonResponse({"success": False, "error": "No autenticado"}, status=401)

    try:
        body = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "JSON inválido"}, status=400)

    pack_id = body.get("pack_id")
    provider = body.get("provider")
    if not pack_id or not provider:
        return JsonResponse({"success": False, "error": "Faltan pack_id o provider"}, status=400)

    try:
        result = checkout_service.start_checkout(user=user, pack_id=pack_id, provider=provider)
        return JsonResponse({"success": True, **result})
    except AppError as e:
        return JsonResponse({"success": False, "error": e.message}, status=e.status_code)
    except Exception as e:
        return JsonResponse({"success": False, "error": f"Error al iniciar el pago: {e}"}, status=502)


@csrf_exempt
@require_http_methods(["POST"])
def confirm_checkout(request):
    user = get_authenticated_user(request)
    if not user:
        return JsonResponse({"success": False, "error": "No autenticado"}, status=401)

    try:
        body = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "JSON inválido"}, status=400)

    provider = body.get("provider")
    provider_reference = body.get("provider_reference")
    extra = body.get("extra") or {}
    if not provider or not provider_reference:
        return JsonResponse(
            {"success": False, "error": "Faltan provider o provider_reference"}, status=400,
        )

    try:
        from ..repositories import transaction_repository
        transaction_obj = transaction_repository.find_by_reference(
            provider=provider.upper(), provider_reference=provider_reference,
        )
        if transaction_obj is not None and transaction_obj.user_id != user.id:
            return JsonResponse({"success": False, "error": "Esta transacción no te pertenece"}, status=403)

        result = checkout_service.confirm_checkout(
            provider=provider, provider_reference=provider_reference, extra=extra,
        )
        return JsonResponse({"success": True, **result})
    except AppError as e:
        return JsonResponse({"success": False, "error": e.message}, status=e.status_code)
    except Exception as e:
        return JsonResponse({"success": False, "error": f"Error al confirmar el pago: {e}"}, status=502)
