"""
services.py — Capa de Servicios de MassSend
════════════════════════════════════════════════════════════════════════════════
PROPÓSITO: Separación de Responsabilidades (SRP) + Principios SOLID aplicados.

En el diseño original, toda la lógica estaba en views.py y admin.py.
Esta capa de servicios extrae la lógica de negocio, dejando:
  - views.py  → solo recibir petición HTTP y devolver respuesta (controlador)
  - services.py → solo lógica de negocio (esta capa)
  - models.py → solo definición de datos

PRINCIPIOS SOLID APLICADOS:
  S — Single Responsibility Principle:
        Cada función/clase tiene UNA sola razón para cambiar.
        MessageService solo gestiona mensajes.
        ContactService solo gestiona contactos.
        WhatsAppGateway solo habla con Node.js.

  O — Open/Closed Principle:
        WhatsAppGateway puede extenderse para soportar otro proveedor
        (ej. Twilio) sin modificar el código de MessageService.
        MessageService recibe el gateway como dependencia, no lo crea.

  L — Liskov Substitution Principle:
        WhatsAppGateway podría sustituirse por MockGateway en tests
        y el sistema funcionaría igual.

  I — Interface Segregation Principle:
        Clientes que solo necesitan leer mensajes importan MessageService.
        Clientes que solo importan contactos usan ContactService.
        No hay una "clase dios" que mezcle todo.

  D — Dependency Inversion Principle:
        MessageService depende de la abstracción (gateway con método send()),
        no de la implementación concreta de requests.post.
════════════════════════════════════════════════════════════════════════════════
"""

import re
import requests
from django.db import transaction
from django.db.models import Q
from django.conf import settings
from .models import Contact, Message, ApiProvider


def normalizar_telefono(raw):
    """
    Limpia y normaliza un número al formato E.164 sin el +.

    Reglas Ecuador (caso principal):
      - Móvil local  09XXXXXXXX  (10 dígitos)  → 5939XXXXXXXX  ✓
      - Fijo  02-07XXXXXXX        (8-9 dígitos) → RECHAZADO
      - Ya con código 5939XXXXXXXX (12 dígitos) → ✓
      - Ya con código 5932-5938XX               → RECHAZADO (fijo)

    Números internacionales (no Ecuador):
      - Deben tener mínimo 11 dígitos (código de país + número móvil).
        Ej: Colombia +573XXXXXXXXX (12d), EEUU +1XXXXXXXXXX (11d).
      - Números cortos sin código de país → RECHAZADOS.

    Devuelve (telefono_limpio, error_msg).  error_msg es None si está ok.
    """
    if not raw:
        return '', 'Teléfono vacío'

    raw_str = str(raw).strip()

    # 1. Detectar notación científica (ej: "1.3071E+12")
    if re.search(r'[Ee][+\-]?\d', raw_str):
        return '', 'Número en notación científica — revisa el formato del CSV'

    # 2. Quitar todo excepto dígitos y '+'
    limpio = re.sub(r'[^\d+]', '', raw_str)

    # 3. Quitar el + inicial si existe
    if limpio.startswith('+'):
        limpio = limpio[1:]

    # 4. Caracteres no numéricos que quedaron
    if not limpio.isdigit():
        return '', 'Teléfono contiene caracteres inválidos'

    # 5. Número local Ecuador (empieza con 0, 8-10 dígitos)
    if re.match(r'^0\d{7,9}$', limpio):
        sin_cero = limpio[1:]
        if not sin_cero.startswith('9'):
            return '', (
                f'Número fijo ({limpio[:3]}...) — los fijos no reciben WhatsApp. '
                f'Los móviles ecuatorianos empiezan con 09XXXXXXXX.'
            )
        limpio = '593' + sin_cero  # → 5939XXXXXXXX (12 dígitos)

    # 6. Número con código Ecuador
    if limpio.startswith('593'):
        if not limpio.startswith('5939'):
            return '', (
                f'Número fijo de Ecuador ({limpio[:5]}...) — '
                f'los fijos no reciben WhatsApp. Solo móviles 5939XXXXXXXX.'
            )
        if len(limpio) != 12:
            return '', (
                f'Móvil Ecuador inválido: {len(limpio)} dígitos '
                f'(se esperan exactamente 12: 5939XXXXXXXX).'
            )
        return limpio, None   # ✓ Ecuatoriano válido

    # 7. Número internacional (no Ecuador)
    #    Mínimo 11 dígitos: código de país (1-3 d) + número móvil (8+ d)
    #    Máximo 15 dígitos (límite E.164)
    if len(limpio) < 11:
        return '', (
            f'Número demasiado corto ({len(limpio)} dígitos). '
            f'Para Ecuador usa 09XXXXXXXX. '
            f'Para otros países incluye el código de país (ej: 573... Colombia, 1... EEUU).'
        )
    if len(limpio) > 15:
        return '', f'Número demasiado largo ({len(limpio)} dígitos, máximo 15).'

    return limpio, None


def destinatarios_campana(campana):
    """
    Contactos activos del dueño de la campaña. target_tags admite varias
    etiquetas separadas por coma: basta con que el contacto tenga una.
    """
    qs = Contact.objects.filter(
        owner_id=campana.owner_id, is_opted_out=False,
    ).exclude(phone_number__contains='@')
    etiquetas = [t.strip() for t in (campana.target_tags or '').split(',') if t.strip()]
    if etiquetas:
        filtro = Q()
        for etiqueta in etiquetas:
            filtro |= Q(tags__icontains=etiqueta)
        qs = qs.filter(filtro)
    return qs


# ─── Gateway: abstracción del transporte hacia WhatsApp ──────────────────────
# Principio O y D: si mañana cambias a Twilio, creas TwilioGateway con el
# mismo método send() y no cambias MessageService.

class WhatsAppGateway:
    """
    Responsabilidad única: enviar mensajes a través del servicio Node.js.
    No sabe nada de base de datos, ni de contactos, ni de campañas.
    """

    def __init__(self):
        base = getattr(settings, 'WHATSAPP_API_URL', 'http://localhost:3001').rstrip('/')
        self.base_url = base

    def send(self, number: str, message: str) -> dict:
        """
        Envía un mensaje de texto. Devuelve dict con success, wpp_message_id.
        Lanza requests.RequestException si Node.js no está disponible.
        """
        resp = requests.post(
            f'{self.base_url}/api/send',
            json={'number': number, 'message': message},
            timeout=20
        )
        resp.raise_for_status()
        return resp.json()

    def status(self) -> dict:
        """Consulta si WhatsApp está conectado."""
        resp = requests.get(f'{self.base_url}/api/status', timeout=5)
        return resp.json()

    def logout(self):
        """Cierra la sesión de WhatsApp en Node.js."""
        requests.post(f'{self.base_url}/api/logout', timeout=10)

    def qr(self) -> dict:
        """Obtiene el QR o código de vinculación actual."""
        resp = requests.get(f'{self.base_url}/api/qr', timeout=5)
        return resp.json()


# ─── Servicio de Mensajes ────────────────────────────────────────────────────

class MessageService:
    """
    Responsabilidad única: orquestar el envío y almacenamiento de mensajes.
    Aplica consistencia transaccional: el mensaje se guarda en DB ANTES de
    llamar a Node.js, y el estado se actualiza DESPUÉS de conocer el resultado.

    CONSISTENCIA TRANSACCIONAL:
    En un sistema distribuido, el riesgo es:
      1. El mensaje llega a Node.js pero falla al guardarse en DB → inconsistencia.
      2. Se guarda en DB pero Node.js no responde → el usuario ve un estado falso.

    Solución aplicada:
      - @transaction.atomic garantiza que el INSERT a DB es atómico.
      - Si Node.js falla, el mensaje queda en estado 'pending' (no se borra).
      - Esto prioriza DISPONIBILIDAD sobre CONSISTENCIA perfecta (ver CAP).
    """

    def __init__(self, gateway: WhatsAppGateway = None):
        # Inyección de dependencia (DIP): recibimos el gateway, no lo creamos
        self.gateway = gateway or WhatsAppGateway()

    @transaction.atomic
    def enviar_mensaje(self, numero: str, texto: str, owner=None) -> dict:
        """
        Envía un mensaje y registra la transacción en la base de datos.

        @transaction.atomic: si ocurre una excepción en cualquier punto de este
        método, Django hace ROLLBACK automático — ningún dato parcial queda
        guardado en la DB.

        Flujo:
          1. Buscar/crear contacto  (dentro de la transacción)
          2. Crear registro Message con estado 'pending'
          3. Llamar a Node.js  (fuera del commit transaccional, pero dentro del bloque)
          4. Dejar 'pending' (Node confirma por /api/send-result/) o 'failed' si Node falla
        """

        # Paso 1: contacto (operación idempotente dentro de la transacción)
        contact, _ = Contact.objects.get_or_create(
            phone_number=numero,
            owner=owner,
            defaults={'full_name': numero}
        )

        # Paso 2: crear registro con estado inicial
        msg_obj = Message.objects.create(
            owner=owner,
            phone_number=numero,
            content=texto,
            direction='outbound',
            delivery_status='pending',
        )

        # Paso 3: intentar enviar a Node.js
        wpp_id = None
        try:
            node_resp = self.gateway.send(numero, texto)
            wpp_id = node_resp.get('wpp_message_id') or None
            if wpp_id:
                msg_obj.wpp_message_id = wpp_id
                msg_obj.save()
        except Exception as e:
            # Node.js no disponible: se registra como fallido.
            # No hacemos raise → la transacción no se revierte
            # (queremos conservar el registro para auditoría)
            print(f'[MessageService] Node.js no disponible: {e}')
            msg_obj.delivery_status = 'failed'
            msg_obj.error_log = str(e)[:200]
            msg_obj.save()
            return {'success': False, 'error': {'message': 'WhatsApp no está disponible'}}

        return {
            'success': True,
            'texto_enviado': texto,
            'wpp_message_id': wpp_id,
        }


# ─── Servicio de Contactos ───────────────────────────────────────────────────

class ContactService:
    """
    Responsabilidad única: gestionar el ciclo de vida de los contactos.
    Separado de MessageService — cambiar cómo se crean contactos no afecta
    cómo se envían mensajes.
    """

    @staticmethod
    @transaction.atomic
    def importar_lote(contactos: list, owner=None) -> dict:
        """
        Importa una lista de contactos en una sola transacción.
        Si un contacto falla, la transacción parcial de ese contacto
        se captura con savepoint para no anular los contactos anteriores.

        CONCURRENCIA: si dos usuarios importan CSV al mismo tiempo,
        update_or_create con phone_number único previene duplicados.
        El ORM de Django usa SELECT FOR UPDATE internamente.
        """
        creados = actualizados = errores = 0
        detalle = []

        for i, row in enumerate(contactos, start=1):
            nombre   = str(row.get('nombre', '')).strip()
            tags     = str(row.get('etiquetas', '')).strip()

            telefono, tel_err = normalizar_telefono(row.get('telefono', ''))
            if tel_err:
                errores += 1
                detalle.append({'fila': i, 'estado': 'error', 'mensaje': tel_err})
                continue

            try:
                # Savepoint individual por fila: un error en fila 5 no deshace la 1-4
                with transaction.atomic():
                    contact, created = Contact.objects.update_or_create(
                        phone_number=telefono,
                        owner=owner,
                        defaults={'full_name': nombre or telefono, 'tags': tags}
                    )
                    if created:
                        creados += 1
                        detalle.append({'fila': i, 'telefono': telefono, 'estado': 'creado'})
                    else:
                        actualizados += 1
                        detalle.append({'fila': i, 'telefono': telefono, 'estado': 'actualizado'})
            except Exception as e:
                errores += 1
                detalle.append({'fila': i, 'telefono': telefono, 'estado': 'error', 'mensaje': str(e)[:80]})

        return {
            'creados': creados,
            'actualizados': actualizados,
            'errores': errores,
            'total': creados + actualizados + errores,
            'detalle': detalle,
        }


# ─── Instancias por defecto (Singleton simple) ───────────────────────────────
# Los servicios son stateless, compartir la instancia es seguro y eficiente.
default_gateway         = WhatsAppGateway()
default_message_service = MessageService(gateway=default_gateway)
default_contact_service = ContactService()
