"""
Vistas del asistente de IA local (Ollama) para MassSend.

Endpoints:
- POST /whatsapp/api/asistente/chat/   → conversación con el asistente
- GET  /whatsapp/api/asistente/health/ → estado de Ollama y del modelo
"""
import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .ai_service import consultar_asistente, estado_ollama
from .views import _get_user


@csrf_exempt
def api_asistente_chat(request):
    user = _get_user(request)
    if not user:
        return JsonResponse({'error': 'No autenticado'}, status=401)
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'JSON inválido.'}, status=400)

    prompt = str(data.get('prompt', '')).strip()
    if not prompt:
        return JsonResponse({'ok': False, 'error': 'Escriba una pregunta para el asistente.'}, status=400)
    if len(prompt) > 2000:
        return JsonResponse({'ok': False, 'error': 'La pregunta es demasiado larga (máximo 2000 caracteres).'}, status=400)

    history = data.get('history') if isinstance(data.get('history'), list) else []

    resultado = consultar_asistente(prompt, history)
    if not resultado.get('ok'):
        status = resultado.pop('status', 502)
        return JsonResponse(resultado, status=status)
    return JsonResponse(resultado)


def api_asistente_health(request):
    if not _get_user(request):
        return JsonResponse({'error': 'No autenticado'}, status=401)
    return JsonResponse(estado_ollama())
