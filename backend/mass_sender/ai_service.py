"""
Asistente de IA local para MassSend (modelo servido por Ollama).

Comunicación síncrona (RPC sobre HTTP): Django actúa como cliente,
envía el prompt a Ollama y espera la respuesta completa antes de
devolverla al frontend. Mismo patrón visto en clase con
ollama-rpc-practica, integrado como capa de servicio (SOLID).
"""
import time
import requests
from django.conf import settings

# Contexto del sistema: el modelo responde SOLO sobre MassSend y ayuda
# a redactar mensajes de campaña. Se antepone a cada prompt del usuario.
SYSTEM_CONTEXT = """Eres el asistente virtual de MassSend, una plataforma web de envío masivo de mensajes de WhatsApp.
Responde SIEMPRE en español, de forma breve (máximo 120 palabras), clara y amable.

Conocimiento del sistema MassSend:
- Menú principal: Inicio, Chat, Campañas, Contactos, Importar CSV, Mensajes, Conectar WhatsApp, Notificaciones, Seguridad (MFA), Créditos y Asistente IA.
- Contactos: se importan desde un archivo CSV en "Importar CSV" y se organizan con etiquetas.
- Campañas: en "Campañas" se crea una campaña con nombre, plantilla de mensaje (admite variables como {{nombre}}), imagen o video opcional y filtro por etiquetas. Luego se ejecuta y los mensajes se envían por WhatsApp uno a uno en segundo plano.
- Conexión WhatsApp: en "Conectar WhatsApp" se escanea un código QR con el teléfono.
- Créditos: 1 crédito = 1 mensaje. Toda cuenta nueva recibe 10 créditos gratis; se compran más con PayPal o PayPhone en la página "Créditos". Sin saldo suficiente la campaña se bloquea.
- Seguridad: registro con verificación por correo, login con Google y verificación en dos pasos (MFA/TOTP) activable en "Seguridad".
- Reportes: entregas, lecturas y fallos por campaña (visible para administradores).

También puedes REDACTAR mensajes para campañas de WhatsApp si el usuario lo pide:
escribe mensajes cortos, cordiales y efectivos, usando la variable {{nombre}} para personalizar
y emojis con moderación. Entrega solo el texto del mensaje listo para copiar.

Si preguntan algo ajeno a MassSend o a la redacción de mensajes, indica amablemente
que solo puedes ayudar con el uso de la plataforma."""


def consultar_asistente(prompt, history=None):
    """
    Envía el prompt (más un breve historial) a Ollama y espera la
    respuesta completa. Devuelve un dict listo para JsonResponse.
    """
    ollama_url = getattr(settings, 'OLLAMA_URL', 'http://localhost:11434').rstrip('/')
    model = getattr(settings, 'OLLAMA_MODEL', 'qwen2.5:0.5b')
    timeout_s = getattr(settings, 'OLLAMA_TIMEOUT_SECONDS', 60)

    # Se arma el prompt: contexto + últimas interacciones + pregunta actual.
    parts = [SYSTEM_CONTEXT, '']
    for turn in (history or [])[-6:]:  # máximo 3 pares pregunta/respuesta
        role = 'Usuario' if turn.get('role') == 'user' else 'Asistente'
        parts.append(f"{role}: {str(turn.get('content', ''))[:500]}")
    parts.append(f"Usuario: {prompt}")
    parts.append('Asistente:')

    start = time.perf_counter()
    try:
        response = requests.post(
            f"{ollama_url}/api/generate",
            json={
                'model': model,
                'prompt': '\n'.join(parts),
                'stream': False,
                'options': {'temperature': 0.3, 'num_predict': 220},
            },
            timeout=timeout_s,
        )
        response.raise_for_status()
        data = response.json()
        latency_ms = round((time.perf_counter() - start) * 1000)
        return {
            'ok': True,
            'answer': str(data.get('response', '')).strip(),
            'model': data.get('model', model),
            'latencyMs': latency_ms,
            'ollamaTotalMs': round(data['total_duration'] / 1_000_000) if data.get('total_duration') else None,
        }
    except requests.Timeout:
        return {
            'ok': False, 'status': 504,
            'error': f'El modelo de IA superó el tiempo máximo de espera de {timeout_s} segundos.',
            'latencyMs': round((time.perf_counter() - start) * 1000),
        }
    except requests.RequestException as exc:
        return {
            'ok': False, 'status': 502,
            'error': 'No fue posible comunicarse con Ollama. Verifique que el servicio esté iniciado y el modelo descargado.',
            'detail': str(exc),
            'latencyMs': round((time.perf_counter() - start) * 1000),
        }


def estado_ollama():
    """Verifica si Ollama está disponible y si el modelo está descargado."""
    ollama_url = getattr(settings, 'OLLAMA_URL', 'http://localhost:11434').rstrip('/')
    model = getattr(settings, 'OLLAMA_MODEL', 'qwen2.5:0.5b')
    try:
        response = requests.get(f"{ollama_url}/api/tags", timeout=3)
        response.raise_for_status()
        models = [m.get('name', '') for m in response.json().get('models', [])]
        return {
            'available': True,
            'model': model,
            'modelDownloaded': any(m.startswith(model.split(':')[0]) for m in models),
            'models': models,
        }
    except requests.RequestException:
        return {'available': False, 'model': model, 'modelDownloaded': False, 'models': []}
