from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.views.decorators.clickjacking import xframe_options_exempt
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages as django_messages, admin
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db import transaction
from django.db.models import Count, Q
from django.conf import settings
import json
import re
import requests
import csv
import io
import hmac
import threading
from datetime import datetime, timedelta
from .models import Contact, Message, ApiProvider, Campaign, CampaignProgress
from .services import default_gateway, default_message_service, destinatarios_campana, normalizar_telefono

def _whatsapp_url(path):
    """Devuelve la URL completa del servicio WhatsApp API."""
    base = getattr(settings, 'WHATSAPP_API_URL', 'http://localhost:3001').rstrip('/')
    return f"{base}{path}"


def _gateway_request_is_trusted(request):
    expected = getattr(settings, 'WHATSAPP_WEBHOOK_TOKEN', '')
    supplied = request.headers.get('Authorization', '')
    return bool(expected) and hmac.compare_digest(supplied, f'Bearer {expected}')


def _require_staff(request):
    user = _get_user(request)
    if not user:
        return JsonResponse({'success': False, 'error': 'Autenticación requerida'}, status=401)
    if not user.is_staff:
        return JsonResponse({'success': False, 'error': 'No autorizado'}, status=403)
    return None


def _get_user(request):
    """
    Devuelve el usuario autenticado ya sea por JWT o por sesión Django.
    Retorna None si no está autenticado.
    """
    # Intentar JWT primero
    from rest_framework_simplejwt.authentication import JWTAuthentication
    from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
    try:
        result = JWTAuthentication().authenticate(request)
        if result:
            return result[0]
    except (InvalidToken, TokenError):
        pass
    # Fallback: sesión Django
    if request.user.is_authenticated:
        return request.user
    return None


def _contactos_de(user):
    """Contactos visibles: los propios, o todos si es staff."""
    qs = Contact.objects.exclude(phone_number__contains='@')
    return qs if user.is_staff else qs.filter(owner=user)


def _mensajes_de(user):
    """Mensajes visibles: los propios, o todos si es staff."""
    qs = Message.objects.exclude(phone_number__contains='@')
    return qs if user.is_staff else qs.filter(owner=user)


def _dueno_conversacion(numero):
    """
    Un mensaje entrante pertenece a quien le escribió por última vez a ese
    número. Si nadie lo hizo queda sin dueño (solo visible para staff).
    """
    return (
        Message.objects.filter(phone_number=numero, direction='outbound', owner__isnull=False)
        .order_by('-sent_at').values_list('owner_id', flat=True).first()
    )


def _es_dueno_o_staff(user, campana):
    """
    True si el usuario puede acceder a la campaña: es el dueño registrado
    o tiene permisos de staff/superusuario (panel administrativo).
    Corrige el IDOR reportado en api_campanas_media, donde cualquier
    usuario autenticado podía leer el archivo de cualquier campaña.
    """
    if user.is_staff:
        return True
    return campana.owner_id == user.id


@xframe_options_exempt
def chat_view(request):
    provider = ApiProvider.objects.filter(is_active=True).first()
    return render(request, 'mass_sender/chat.html', {'provider': provider})

def api_leer_mensajes(request):
    denied = _require_staff(request)
    if denied:
        return denied
    provider = ApiProvider.objects.filter(is_active=True).first()
    # Excluir contactos con JIDs invalidos (@lid, @g.us, @newsletter, etc.)
    contacts = Contact.objects.exclude(phone_number__contains='@').order_by('-created_at')
    mensajes_dict = {}

    for contact in contacts:
        num = contact.phone_number
        if num.startswith('+'):
            num = num[1:]

        mensajes_qs = Message.objects.filter(
            phone_number=contact.phone_number
        ).exclude(phone_number__contains='@').order_by('sent_at')

        msgs_list = []
        for m in mensajes_qs:
            msgs_list.append({
                "direccion":      "OUT" if m.direction == "outbound" else "IN",
                # 'tipo' es el campo que usa el JS para detectar si el mensaje es enviado
                "tipo":           "enviado" if m.direction == "outbound" else "recibido",
                "texto":          m.content or "",
                "fecha":          m.sent_at.strftime('%Y-%m-%d') if m.sent_at else "",
                "hora":           m.sent_at.strftime('%H:%M') if m.sent_at else "",
                # 'status' es el campo que usa el JS para mostrar los ticks
                "status":         m.delivery_status or "sent",
                "wpp_message_id": getattr(m, 'wpp_message_id', '') or "",
            })

        nombre_display = contact.full_name or ('+' + num)

        mensajes_dict[num] = {
            "nombre":      nombre_display,
            # custom_name es lo que el JS usa en la lista de chats
            "custom_name": contact.full_name or "",
            "foto":        f"https://ui-avatars.com/api/?name={contact.full_name or num}&background=4f46e5&color=fff",
            "no_leidos":   0,
            "mensajes":    msgs_list,
            "etiqueta":    contact.tags or "",
        }

    return JsonResponse({
        "has_changes": True,
        "timestamp":   999999999,
        "mensajes":    mensajes_dict,
        "account_info": {
            "business_name":  "MassSend",
            "display_number": provider.display_number if provider else "0000"
        }
    })

@csrf_exempt
def api_enviar_whatsapp(request):
    """
    Vista: recibe la petición HTTP y delega la lógica al servicio.
    Principio SRP: la vista NO sabe cómo se envía el mensaje, solo coordina.
    Principio D: depende de default_message_service (abstracción), no de requests.post.
    Solo staff: es el Chat del panel, que usa el número único conectado.

    CONSISTENCIA TRANSACCIONAL:
    La lógica atómica está en MessageService.enviar_mensaje(), decorada con
    @transaction.atomic. Si el proceso falla a mitad, Django hace rollback.
    """
    denied = _require_staff(request)
    if denied:
        return denied
    if request.method == 'POST':
        try:
            data   = json.loads(request.body)
            numero = data.get('to')
            mensaje = data.get('message')

            if not numero or not mensaje:
                return JsonResponse({"success": False, "error": {"message": "Faltan parámetros"}})

            # Delegar al servicio — vista queda limpia y testeable
            resultado = default_message_service.enviar_mensaje(numero, mensaje, owner=_get_user(request))
            return JsonResponse(resultado)

        except Exception as e:
            return JsonResponse({"success": False, "error": {"message": str(e)}})
    return JsonResponse({"success": False})

@csrf_exempt
def api_webhook(request):
    """
    Recibe mensajes entrantes desde Node.js.

    CONSISTENCIA TRANSACCIONAL con @transaction.atomic:
    El contacto y el mensaje se crean en una sola transacción.
    Si falla la creación del mensaje, el contacto tampoco se crea
    (o viceversa) — no quedan registros huérfanos.

    CONCURRENCIA: si dos mensajes del mismo número llegan simultáneamente,
    get_or_create usa SELECT + INSERT atómico — el ORM garantiza que no
    se creen dos contactos con el mismo número (unique constraint).
    """
    if not _gateway_request_is_trusted(request):
        return JsonResponse({'success': False, 'error': 'No autorizado'}, status=401)

    if request.method == 'POST':
        try:
            data   = json.loads(request.body)
            numero = data.get('from')
            mensaje = data.get('body')

            if not numero or '@' in str(numero):
                return JsonResponse({"success": True, "skipped": True})

            if numero and mensaje:
                with transaction.atomic():
                    owner_id = _dueno_conversacion(numero)
                    # get_or_create es atómico: no produce duplicados bajo concurrencia
                    contact, _ = Contact.objects.get_or_create(
                        phone_number=numero,
                        owner_id=owner_id,
                        defaults={'full_name': numero}
                    )
                    Message.objects.create(
                        owner_id=owner_id,
                        phone_number=numero,
                        content=mensaje,
                        direction='inbound'
                    )
            return JsonResponse({"success": True})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})
    return JsonResponse({"success": False})

@csrf_exempt
def api_message_ack(request):
    """
    Llamado por Node.js cuando cambia el estado de entrega de un mensaje.
    ack: -1=fallido, 0=pendiente, 1=enviado, 2=entregado, 3=leido
    Intenta actualizar por wpp_message_id primero; si no encuentra,
    usa el mensaje saliente mas reciente de ese numero como fallback.
    """
    if not _gateway_request_is_trusted(request):
        return JsonResponse({'success': False, 'error': 'No autorizado'}, status=401)

    if request.method != 'POST':
        return JsonResponse({"success": False}, status=405)

    try:
        data   = json.loads(request.body)
        wpp_id = (data.get('wpp_message_id') or '').strip()
        number = (data.get('number') or '').strip()
        status = data.get('status', '')

        ACK_MAP = {
            '-1': 'failed',
            '0':  'pending',
            '1':  'sent',
            '2':  'delivered',
            '3':  'read',
        }
        ack_num = str(data.get('ack', ''))
        if ack_num in ACK_MAP:
            status = ACK_MAP[ack_num]

        if not status:
            return JsonResponse({"success": False, "error": "Sin status/ack"}, status=400)

        PRIORITY = {'failed': 0, 'pending': 0, 'sent': 1, 'delivered': 2, 'read': 3}

        updated = 0

        # 1. Intentar actualizar por wpp_message_id
        if wpp_id:
            updated = Message.objects.filter(wpp_message_id=wpp_id).update(delivery_status=status)

        # 2. Fallback: buscar el mensaje saliente más reciente que aún no haya alcanzado ese estado
        if updated == 0 and number:
            new_p = PRIORITY.get(status, 0)

            # Preferir mensajes cuyo estado actual sea menor al nuevo (para no retroceder)
            estados_inferiores = [s for s, p in PRIORITY.items() if p < new_p]

            msg = Message.objects.filter(
                phone_number__icontains=number,
                direction='outbound',
                delivery_status__in=estados_inferiores if estados_inferiores else ['sent', 'pending']
            ).order_by('-sent_at').first()

            # Si no encontró con filtro de estado, intentar sin filtro (para el caso de 'failed')
            if not msg and status == 'failed':
                msg = Message.objects.filter(
                    phone_number__icontains=number,
                    direction='outbound'
                ).order_by('-sent_at').first()

            if msg:
                msg.delivery_status = status
                if wpp_id and not msg.wpp_message_id:
                    msg.wpp_message_id = wpp_id
                msg.save()
                updated = 1

        return JsonResponse({"success": True, "updated": updated})

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@csrf_exempt
def api_send_result(request):
    """
    Llamado por Node.js cuando un mensaje de la cola fue procesado (enviado o fallido).
    Actualiza el estado real del mensaje en Django.
    """
    if not _gateway_request_is_trusted(request):
        return JsonResponse({'success': False, 'error': 'No autorizado'}, status=401)

    if request.method != 'POST':
        return JsonResponse({"success": False}, status=405)
    try:
        data   = json.loads(request.body)
        number = data.get('number', '').strip()
        status = data.get('status', '')       # 'sent' o 'failed'
        wpp_id = data.get('wpp_message_id', '') or ''

        if not number or not status:
            return JsonResponse({"success": False, "error": "Faltan parametros"}, status=400)

        # La cola de Node es FIFO: el resultado corresponde al 'pending' más antiguo
        msg = Message.objects.filter(
            phone_number__icontains=number,
            direction='outbound',
            delivery_status='pending'
        ).order_by('sent_at').first()

        if msg:
            msg.delivery_status = status
            if status == 'failed':
                msg.error_log = str(data.get('error') or '')[:500]
            if wpp_id and not msg.wpp_message_id:
                msg.wpp_message_id = wpp_id
            msg.save()

        return JsonResponse({"success": True, "updated": 1 if msg else 0})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@csrf_exempt
def dummy_success(request):
    return JsonResponse({"success": True, "status": "ok"})


@csrf_exempt
def api_cambiar_numero(request):
    """Cierra la sesión de WhatsApp en Node.js."""
    denied = _require_staff(request)
    if denied:
        return denied
    if request.method == 'POST':
        try:
            requests.post(_whatsapp_url('/api/logout'), timeout=10)
            return JsonResponse({"success": True})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})
    return JsonResponse({"success": False, "error": "Método no permitido"})


def api_qr_status(request):
    """Proxy: devuelve el QR y/o código de vinculación desde Node.js."""
    denied = _require_staff(request)
    if denied:
        return denied
    try:
        resp = requests.get(_whatsapp_url('/api/qr'), timeout=5)
        data = resp.json()
        return JsonResponse(data)
    except Exception:
        return JsonResponse({"ready": False, "has_qr": False, "qr": None, "has_pairing": False, "pairing_code": None})


@csrf_exempt
def api_request_pairing(request):
    """Solicita un código de vinculación por número de teléfono a Node.js."""
    denied = _require_staff(request)
    if denied:
        return denied
    if request.method == 'POST':
        try:
            data  = json.loads(request.body)
            phone = data.get('phone', '').strip()
            if not phone:
                return JsonResponse({"success": False, "error": "Falta el número de teléfono"})
            resp = requests.post(
                _whatsapp_url('/api/request-pairing'),
                json={"phone": phone},
                timeout=15
            )
            return JsonResponse(resp.json())
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})
    return JsonResponse({"success": False, "error": "Método no permitido"})


def cambiar_numero_admin_view(request):
    """Página del admin para cambiar el número de WhatsApp con QR en pantalla."""
    context = admin.site.each_context(request)
    context['title'] = 'Cambiar Número de WhatsApp'

    # Estado actual
    try:
        status_resp = requests.get(_whatsapp_url('/api/status'), timeout=3)
        context['wa_connected'] = status_resp.json().get('ready', False)
    except Exception:
        context['wa_connected'] = False

    provider = ApiProvider.objects.filter(is_active=True).first()
    context['numero_actual'] = provider.display_number if provider else '—'

    return render(request, 'mass_sender/cambiar_numero.html', context)




# ─────────────────────────────────────────────
# IMPORTAR CONTACTOS DESDE CSV
# ─────────────────────────────────────────────
@staff_member_required
def import_contacts(request):
    request.current_app = admin.site.name
    result = None
    admin_context = admin.site.each_context(request)

    if request.method == 'POST':

        # ── Rama A: datos ya procesados desde el modal de preview ──────────
        contacts_json = request.POST.get('contacts_json')
        if contacts_json:
            try:
                contacts_data = json.loads(contacts_json)
            except Exception:
                django_messages.error(request, 'Error al procesar los datos. Intenta de nuevo.')
                return redirect('/admin/import-contacts/')

            creados = actualizados = errores = 0
            detalle = []

            for i, row in enumerate(contacts_data, start=1):
                raw_tel   = str(row.get('telefono',  '')).strip()
                nombre    = str(row.get('nombre',    '')).strip()
                etiquetas = str(row.get('etiquetas', '')).strip()
                notas     = str(row.get('notas',     '')).strip()

                telefono, tel_err = normalizar_telefono(raw_tel)
                if tel_err:
                    errores += 1
                    detalle.append({'fila': i, 'telefono': raw_tel or '—', 'nombre': nombre,
                                    'estado': 'error', 'mensaje': tel_err})
                    continue

                try:
                    defaults = {'full_name': nombre or telefono, 'tags': etiquetas}
                    if notas:
                        defaults['custom_data'] = {'notas': notas}

                    contact, created = Contact.objects.update_or_create(
                        phone_number=telefono, owner=request.user, defaults=defaults)

                    if created:
                        creados += 1; estado = 'creado'; msg = 'Contacto nuevo'
                    else:
                        actualizados += 1; estado = 'actualizado'; msg = 'Datos actualizados'

                    detalle.append({'fila': i, 'telefono': telefono, 'nombre': nombre,
                                    'estado': estado, 'mensaje': msg})
                except Exception as e:
                    errores += 1
                    detalle.append({'fila': i, 'telefono': telefono, 'nombre': nombre,
                                    'estado': 'error', 'mensaje': str(e)[:80]})

            result = {
                'creados': creados, 'actualizados': actualizados,
                'errores': errores,
                'total': creados + actualizados + errores,
                'detalle': detalle,
            }
            return render(request, 'mass_sender/import_contacts.html', {
                **admin_context, 'title': 'Importar Contactos CSV', 'result': result,
            })

        # ── Rama B: subida de archivo CSV clásica (fallback) ───────────────
        csv_file = request.FILES.get('csv_file')
        separator = request.POST.get('separator', ',')
        skip_header = request.POST.get('skip_header') == 'on'

        if not csv_file:
            django_messages.error(request, 'No se seleccionó ningún archivo.')
            return redirect('/admin/import-contacts/')

        if not csv_file.name.lower().endswith(('.csv', '.txt')):
            django_messages.error(request, 'El archivo debe ser .csv o .txt')
            return redirect('/admin/import-contacts/')

        try:
            raw = csv_file.read().decode('utf-8-sig', errors='replace')
        except Exception:
            django_messages.error(request, 'No se pudo leer el archivo. Asegúrate de que esté en UTF-8.')
            return redirect('/admin/import-contacts/')

        reader = csv.reader(io.StringIO(raw), delimiter=separator)
        filas = list(reader)

        if skip_header and filas:
            filas = filas[1:]

        creados = 0
        actualizados = 0
        errores = 0
        detalle = []

        for i, fila in enumerate(filas, start=2 if skip_header else 1):
            if not fila or all(c.strip() == '' for c in fila):
                continue

            raw_tel   = fila[0].strip() if len(fila) > 0 else ''
            nombre    = fila[1].strip() if len(fila) > 1 else ''
            etiquetas = fila[2].strip() if len(fila) > 2 else ''
            notas     = fila[3].strip() if len(fila) > 3 else ''

            telefono, tel_err = normalizar_telefono(raw_tel)
            if tel_err:
                errores += 1
                detalle.append({'fila': i, 'telefono': raw_tel or '—', 'nombre': nombre,
                                'estado': 'error', 'mensaje': tel_err})
                continue

            try:
                defaults = {
                    'full_name': nombre or telefono,
                    'tags': etiquetas,
                }
                if notas:
                    defaults['custom_data'] = {'notas': notas}

                contact, created = Contact.objects.update_or_create(
                    phone_number=telefono,
                    owner=request.user,
                    defaults=defaults,
                )
                if created:
                    creados += 1
                    estado = 'creado'
                    msg = 'Contacto nuevo'
                else:
                    actualizados += 1
                    estado = 'actualizado'
                    msg = 'Datos actualizados'

                detalle.append({'fila': i, 'telefono': telefono, 'nombre': nombre, 'estado': estado, 'mensaje': msg})

            except Exception as e:
                errores += 1
                detalle.append({'fila': i, 'telefono': telefono, 'nombre': nombre, 'estado': 'error', 'mensaje': str(e)[:80]})

        result = {
            'creados': creados,
            'actualizados': actualizados,
            'errores': errores,
            'total': creados + actualizados + errores,
            'detalle': detalle,
        }

    return render(request, 'mass_sender/import_contacts.html', {
        **admin_context,
        'title': 'Importar Contactos CSV',
        'result': result,
    })


# ─────────────────────────────────────────────
# API DE REPORTES (JSON)
# ─────────────────────────────────────────────
@csrf_exempt
def api_reportes(request):
    user = _get_user(request)
    if not user:
        return JsonResponse({'error': 'No autenticado'}, status=401)
    desde_str  = request.GET.get('desde', '')
    hasta_str  = request.GET.get('hasta', '')
    status_fil = request.GET.get('status', '')

    hoy = timezone.now().date()
    try:
        desde = datetime.strptime(desde_str, '%Y-%m-%d').date() if desde_str else hoy - timedelta(days=30)
        hasta = datetime.strptime(hasta_str, '%Y-%m-%d').date() if hasta_str else hoy
    except ValueError:
        desde = hoy - timedelta(days=30)
        hasta = hoy

    qs = _mensajes_de(user).filter(
        sent_at__date__gte=desde,
        sent_at__date__lte=hasta,
    )

    if status_fil:
        qs = qs.filter(delivery_status=status_fil)

    outbound = qs.filter(direction='outbound')
    inbound  = qs.filter(direction='inbound')

    enviados   = outbound.count()
    recibidos  = inbound.count()
    entregados = outbound.filter(delivery_status='delivered').count()
    leidos     = outbound.filter(delivery_status='read').count()
    fallidos   = outbound.filter(delivery_status='failed').count()
    enviados_puro = outbound.filter(delivery_status='sent').count()

    resumen = {
        'enviados': enviados,
        'recibidos': recibidos,
        'entregados': entregados,
        'leidos': leidos,
        'fallidos': fallidos,
        'enviados_puro': enviados_puro,
    }

    # Por día
    from django.db.models.functions import TruncDate
    por_dia_qs = (
        qs.annotate(dia=TruncDate('sent_at'))
        .values('dia')
        .annotate(
            enviados=Count('id', filter=Q(direction='outbound')),
            recibidos=Count('id', filter=Q(direction='inbound')),
        )
        .order_by('dia')
    )
    por_dia = [
        {
            'dia': str(row['dia']),
            'enviados': row['enviados'],
            'recibidos': row['recibidos'],
        }
        for row in por_dia_qs if row['dia']
    ]

    # Últimos 100 mensajes salientes
    ultimos = outbound.order_by('-sent_at')[:100]
    mensajes = []
    for m in ultimos:
        # Buscar nombre de contacto
        contact = _contactos_de(user).filter(phone_number=m.phone_number).first()
        campana = m.campaign.name if m.campaign else ''
        mensajes.append({
            'id': m.id,
            'telefono': m.phone_number,
            'nombre': contact.full_name if contact else m.phone_number,
            'campana': campana,
            'mensaje': m.content[:120] if m.content else '',
            'status': m.delivery_status or 'sent',
            'fecha': m.sent_at.strftime('%d/%m/%Y %H:%M') if m.sent_at else '',
        })

    return JsonResponse({
        'resumen': resumen,
        'por_dia': por_dia,
        'mensajes': mensajes,
    })


# ─────────────────────────────────────────────
# VISTA DE REPORTES (página HTML en el admin)
# ─────────────────────────────────────────────
@staff_member_required
def chat_embed_view(request):
    request.current_app = admin.site.name
    return render(request, 'mass_sender/chat_embed.html', {
        **admin.site.each_context(request),
        'title': 'Chat WhatsApp',
    })


@staff_member_required
def reportes_view(request):
    request.current_app = admin.site.name
    return render(request, 'mass_sender/reportes.html', {
        **admin.site.each_context(request),
        'title': 'Reportes de Mensajeria',
    })


# ─────────────────────────────────────────────
# API PROGRESO DE CAMPAÑA (JSON polling)
# ─────────────────────────────────────────────
@csrf_exempt
def api_campaign_progress(request, campaign_id):
    """
    Devuelve el progreso actual de una campaña en formato JSON.
    Útil para hacer polling desde el frontend y mostrar una barra de progreso.
    """
    user = _get_user(request)
    if not user:
        return JsonResponse({'error': 'No autenticado'}, status=401)
    from .models import Campaign, CampaignProgress
    try:
        campaign = Campaign.objects.get(id=campaign_id)
        if not _es_dueno_o_staff(user, campaign):
            return JsonResponse({'error': 'No autorizado'}, status=403)
        progress = CampaignProgress.objects.get(campaign=campaign)
        return JsonResponse({
            'success': True,
            'campaign_id': campaign_id,
            'campaign_name': campaign.name,
            'status': campaign.status,
            'total': progress.total,
            'sent': progress.sent,
            'failed': progress.failed,
            'is_running': progress.is_running,
            'percent': int((progress.sent + progress.failed) / progress.total * 100) if progress.total > 0 else 0,
            'last_error': progress.last_error,
            'started_at': progress.started_at.isoformat() if progress.started_at else None,
            'finished_at': progress.finished_at.isoformat() if progress.finished_at else None,
        })
    except Campaign.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Campaña no encontrada'}, status=404)
    except CampaignProgress.DoesNotExist:
        return JsonResponse({
            'success': True,
            'campaign_id': campaign_id,
            'status': Campaign.objects.get(id=campaign_id).status,
            'is_running': False,
            'total': 0, 'sent': 0, 'failed': 0, 'percent': 0,
            'last_error': None,
        })


# ─────────────────────────────────────────────
# VISTA: MONITOR EN TIEMPO REAL DE CAMPAÑA
# ─────────────────────────────────────────────
@staff_member_required
def campaign_monitor_view(request, campaign_id):
    """
    Pagina de monitoreo en tiempo real del envio de una campana.
    Usa polling al endpoint api_campaign_progress para mostrar
    barra de progreso, contadores y tiempo estimado.
    """
    from .models import Campaign
    try:
        campaign = Campaign.objects.get(id=campaign_id)
    except Campaign.DoesNotExist:
        from django.http import Http404
        raise Http404("Campana no encontrada")

    return render(request, 'mass_sender/campaign_monitor.html', {
        **admin.site.each_context(request),
        'title': f'Monitor — {campaign.name}',
        'campaign_id': campaign_id,
        'campaign_name': campaign.name,
    })


# ═══════════════════════════════════════════════════════════════════════════
# API REST PARA REACT — sin interfaz Django, solo JSON
# ═══════════════════════════════════════════════════════════════════════════

# ── Autenticación ────────────────────────────────────────────────────────

@csrf_exempt
def api_logout(request):
    logout(request)
    return JsonResponse({'success': True})


def api_me(request):
    # Intentar autenticación por JWT primero
    from rest_framework_simplejwt.authentication import JWTAuthentication
    from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
    try:
        auth = JWTAuthentication()
        result = auth.authenticate(request)
        if result:
            user, token = result
            return JsonResponse({
                'authenticated': True,
                'user': {
                    'username': user.username,
                    'email': user.email,
                    'nombre': token.get('nombre', user.get_full_name()),
                    'foto': token.get('foto', ''),
                    'isStaff': user.is_staff,
                }
            })
    except (InvalidToken, TokenError):
        pass
    # Fallback: sesión Django normal
    if request.user.is_authenticated:
        return JsonResponse({
            'authenticated': True,
            'user': {
                'username': request.user.username,
                'email': request.user.email,
                'isStaff': request.user.is_staff,
            }
        })
    return JsonResponse({'authenticated': False}, status=401)


# ── Campañas ─────────────────────────────────────────────────────────────

@csrf_exempt
def api_campanas_list(request):
    user = _get_user(request)
    if not user:
        return JsonResponse({'error': 'No autenticado'}, status=401)

    if request.method == 'GET':
        # Aislamiento por dueño: cada usuario ve solo sus propias campañas,
        # salvo el staff/superusuario, que ve todas (panel administrativo).
        campanas = Campaign.objects.all() if user.is_staff else Campaign.objects.filter(owner=user)
        campanas = campanas.order_by('-created_at')
        data = []
        for c in campanas:
            try:
                p = c.progress
                progreso = {
                    'total': p.total, 'sent': p.sent, 'failed': p.failed,
                    'is_running': p.is_running,
                    'percent': int((p.sent + p.failed) / p.total * 100) if p.total > 0 else 0
                }
            except CampaignProgress.DoesNotExist:
                progreso = {'total': 0, 'sent': 0, 'failed': 0, 'is_running': False, 'percent': 0}

            data.append({
                'id': c.id,
                'nombre': c.name,
                'status': c.status,
                'mensaje': c.message_template[:80] + '...' if len(c.message_template) > 80 else c.message_template,
                'target_tags': c.target_tags or '',
                'scheduled_at': c.scheduled_at.isoformat() if c.scheduled_at else None,
                'created_at': c.created_at.strftime('%d/%m/%Y %H:%M'),
                'progreso': progreso,
            })
        return JsonResponse({'campanas': data})

    if request.method == 'POST':
        try:
            # Soporta tanto JSON como multipart/form-data (para subir archivos)
            ct = request.content_type or ''
            if 'multipart' in ct or 'form' in ct:
                data = request.POST
                media_file = request.FILES.get('media_file')
            else:
                data = json.loads(request.body)
                media_file = None
            with transaction.atomic():
                campana = Campaign.objects.create(
                    owner=user,
                    name=data.get('nombre', '').strip(),
                    message_template=data.get('mensaje', '').strip(),
                    target_tags=data.get('target_tags', '').strip() or None,
                    media_url=data.get('media_url', '').strip() or None,
                    status='draft',
                )
                if media_file:
                    # Almacenamiento distribuido: la foto/video se guarda en
                    # PocketBase y la campaña conserva solo la URL pública.
                    # Si PocketBase no responde, respaldo en media/ local.
                    from .pocketbase_media import subir_media_campana
                    pb_url = subir_media_campana(media_file, campaign_id=campana.id, title=campana.name)
                    if pb_url:
                        campana.media_url = pb_url
                    else:
                        campana.media_file = media_file
                    campana.save()
            return JsonResponse({'success': True, 'id': campana.id}, status=201)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    return JsonResponse({'error': 'Método no permitido'}, status=405)


@csrf_exempt
def api_campanas_detail(request, pk):
    user = _get_user(request)
    if not user:
        return JsonResponse({'error': 'No autenticado'}, status=401)
    try:
        campana = Campaign.objects.get(pk=pk)
    except Campaign.DoesNotExist:
        return JsonResponse({'error': 'No encontrada'}, status=404)
    if not _es_dueno_o_staff(user, campana):
        return JsonResponse({'error': 'No autorizado'}, status=403)

    if request.method == 'GET':
        # media_effective: archivo subido tiene prioridad sobre URL manual
        media_effective = ''
        media_file_name = ''
        if campana.media_file:
            try:
                media_effective = request.build_absolute_uri(campana.media_file.url)
                media_file_name = campana.media_file.name.split('/')[-1]
            except Exception:
                pass
        elif campana.media_url:
            from .pocketbase_media import es_url_pocketbase
            if es_url_pocketbase(campana.media_url):
                # Archivo protegido en PocketBase: el navegador debe pasar
                # por el endpoint autenticado del backend (nunca URL directa).
                media_effective = request.build_absolute_uri(
                    f'/whatsapp/api/campanas/{campana.id}/media/'
                )
                media_file_name = campana.media_url.split('/')[-1]
            else:
                media_effective = campana.media_url
        return JsonResponse({
            'id': campana.id,
            'nombre': campana.name,
            'mensaje': campana.message_template,
            'status': campana.status,
            'target_tags': campana.target_tags or '',
            'media_url': campana.media_url or '',
            'media_file_url': media_effective,
            'media_file_name': media_file_name,
            'scheduled_at': campana.scheduled_at.isoformat() if campana.scheduled_at else None,
            'created_at': campana.created_at.strftime('%d/%m/%Y %H:%M'),
        })

    if request.method == 'PUT':
        try:
            ct = request.content_type or ''
            if 'multipart' in ct or 'form' in ct:
                # Django no parsea request.POST/FILES en PUT — usar MultiPartParser
                from django.http.multipartparser import MultiPartParser as _MP
                _data, _files = _MP(request.META, request, request.upload_handlers).parse()
                media_file = _files.get('media_file')
            else:
                _data = json.loads(request.body)
                media_file = None

            def _get(key, default):
                v = _data.get(key)
                return v if v is not None else default

            with transaction.atomic():
                campana.name             = _get('nombre',      campana.name)
                campana.message_template = _get('mensaje',     campana.message_template)
                campana.target_tags      = _get('target_tags', campana.target_tags) or None
                campana.media_url        = _get('media_url',   campana.media_url)   or None
                if media_file:
                    from .pocketbase_media import subir_media_campana
                    pb_url = subir_media_campana(media_file, campaign_id=campana.id, title=campana.name)
                    if pb_url:
                        campana.media_url = pb_url
                        campana.media_file = None  # el archivo vive en PocketBase
                    else:
                        campana.media_file = media_file
                campana.save()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    if request.method == 'DELETE':
        with transaction.atomic():
            campana.delete()
        return JsonResponse({'success': True})

    return JsonResponse({'error': 'Método no permitido'}, status=405)


def api_campanas_media(request, pk):
    """
    Entrega el archivo (foto/video) de una campaña almacenado en PocketBase.
    Protección de archivos: la colección es privada, por lo que la URL de
    PocketBase no funciona directamente; SOLO este endpoint, que valida al
    usuario autenticado (sesión o JWT), puede entregar el contenido.
    """
    from django.http import HttpResponse
    from .pocketbase_media import descargar_media, es_url_pocketbase

    user = _get_user(request)
    if not user:
        return JsonResponse({'error': 'No autenticado'}, status=401)
    try:
        campana = Campaign.objects.get(pk=pk)
    except Campaign.DoesNotExist:
        return JsonResponse({'error': 'No encontrada'}, status=404)
    if not _es_dueno_o_staff(user, campana):
        return JsonResponse({'error': 'No autorizado'}, status=403)
    if not campana.media_url or not es_url_pocketbase(campana.media_url):
        return JsonResponse({'error': 'La campaña no tiene archivo en PocketBase.'}, status=404)

    contenido, content_type = descargar_media(campana.media_url)
    if contenido is None:
        return JsonResponse({'error': 'No fue posible obtener el archivo desde PocketBase.'}, status=502)
    response = HttpResponse(contenido, content_type=content_type)
    filename = campana.media_url.split('/')[-1]
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response


@csrf_exempt
def api_campanas_ejecutar(request, pk):
    user = _get_user(request)
    if not user:
        return JsonResponse({'error': 'No autenticado'}, status=401)
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    try:
        from .admin import _send_campaign_background, get_campaign_lock
        import os

        campana = Campaign.objects.get(pk=pk)
        if not _es_dueno_o_staff(user, campana):
            return JsonResponse({'error': 'No autorizado'}, status=403)

        if campana.status == 'running':
            return JsonResponse({'success': False, 'error': 'La campaña ya está en ejecución'})

        contact_ids = list(destinatarios_campana(campana).values_list('id', flat=True))
        if not contact_ids:
            return JsonResponse({'success': False, 'error': 'No hay contactos activos para esta campaña'})

        # Sin WhatsApp conectado todos los envíos fallarían: se corta antes
        # de cobrar créditos.
        try:
            whatsapp_listo = default_gateway.status().get('ready')
        except Exception:
            whatsapp_listo = False
        if not whatsapp_listo:
            return JsonResponse({'success': False, 'error': 'WhatsApp no está conectado'}, status=503)

        campaign_lock = get_campaign_lock(campana.id)
        if not campaign_lock.acquire(blocking=False):
            return JsonResponse({'success': False, 'error': 'La campaña ya está siendo ejecutada'})

        # Cobro de créditos: 1 crédito = 1 mensaje. Los admins (staff)
        # no consumen créditos. Si no alcanza el saldo, se libera el
        # lock recién adquirido y se corta antes de lanzar el hilo.
        cobrado_a = None
        if not user.is_staff:
            from billing.services import wallet_service
            from billing.utils.errors import AppError
            try:
                wallet_service.spend_credits(
                    user, len(contact_ids), reason=f'Campaña "{campana.name}" (#{campana.id})',
                )
            except AppError as e:
                campaign_lock.release()
                return JsonResponse({'success': False, 'error': e.message}, status=402)
            cobrado_a = user

        def hilo_target(cid, cids, lock, cobrado):
            try:
                _send_campaign_background(cid, cids, cobrado_a=cobrado)
            finally:
                lock.release()

        hilo = threading.Thread(
            target=hilo_target,
            args=(campana.id, contact_ids, campaign_lock, cobrado_a),
            daemon=True,
            name=f'Campaign-{campana.id}'
        )
        hilo.start()

        return JsonResponse({
            'success': True,
            'message': f'Campaña iniciada para {len(contact_ids)} contactos'
        })
    except Campaign.DoesNotExist:
        return JsonResponse({'error': 'Campaña no encontrada'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ── Contactos ─────────────────────────────────────────────────────────────

@csrf_exempt
def api_contactos_list(request):
    user = _get_user(request)
    if not user:
        return JsonResponse({'error': 'No autenticado'}, status=401)

    if request.method == 'GET':
        busqueda = request.GET.get('q', '')
        tag = request.GET.get('tag', '')
        estado = request.GET.get('estado', '')
        page = int(request.GET.get('page', 1))
        per_page = 50

        qs = _contactos_de(user).order_by('-created_at')
        if busqueda:
            qs = qs.filter(Q(phone_number__icontains=busqueda) | Q(full_name__icontains=busqueda))
        if tag:
            qs = qs.filter(tags__icontains=tag)
        if estado == 'activo':
            qs = qs.filter(is_opted_out=False)
        elif estado == 'optout':
            qs = qs.filter(is_opted_out=True)

        total = qs.count()
        contactos = qs[(page - 1) * per_page: page * per_page]

        # Obtener etiquetas únicas para los filtros
        all_tags_raw = _contactos_de(user).exclude(tags__isnull=True).exclude(tags='').values_list('tags', flat=True)
        tags_set = set()
        for t in all_tags_raw:
            for part in t.split(','):
                clean = part.strip()
                if clean:
                    tags_set.add(clean)

        return JsonResponse({
            'contactos': [{
                'id': c.id,
                'telefono': c.phone_number,
                'nombre': c.full_name or '',
                'tags': c.tags or '',
                'is_opted_out': c.is_opted_out,
                'created_at': c.created_at.strftime('%d/%m/%Y'),
            } for c in contactos],
            'total': total,
            'page': page,
            'pages': (total + per_page - 1) // per_page,
            'tags_disponibles': sorted(tags_set),
        })

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            telefono, tel_err = normalizar_telefono(data.get('telefono', ''))
            if tel_err:
                return JsonResponse({'success': False, 'error': tel_err}, status=400)
            with transaction.atomic():
                contact, created = Contact.objects.update_or_create(
                    phone_number=telefono,
                    owner=user,
                    defaults={
                        'full_name': data.get('nombre', '').strip() or telefono,
                        'tags': data.get('tags', '').strip() or None,
                    }
                )
            return JsonResponse({'success': True, 'id': contact.id, 'created': created}, status=201)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    return JsonResponse({'error': 'Método no permitido'}, status=405)


@csrf_exempt
def api_contactos_detail(request, pk):
    user = _get_user(request)
    if not user:
        return JsonResponse({'error': 'No autenticado'}, status=401)
    try:
        contacto = _contactos_de(user).get(pk=pk)
    except Contact.DoesNotExist:
        return JsonResponse({'error': 'No encontrado'}, status=404)

    if request.method == 'PUT':
        try:
            data = json.loads(request.body)
            with transaction.atomic():
                contacto.full_name = data.get('nombre', contacto.full_name)
                contacto.tags = data.get('tags', contacto.tags) or None
                contacto.is_opted_out = data.get('is_opted_out', contacto.is_opted_out)
                contacto.save()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    if request.method == 'DELETE':
        with transaction.atomic():
            contacto.delete()
        return JsonResponse({'success': True})

    return JsonResponse({'error': 'Método no permitido'}, status=405)


@csrf_exempt
def api_contactos_bulk_delete(request):
    """Elimina múltiples contactos por lista de IDs."""
    user = _get_user(request)
    if not user:
        return JsonResponse({'error': 'No autenticado'}, status=401)
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    try:
        data = json.loads(request.body)
        ids = data.get('ids', [])
        if not ids:
            return JsonResponse({'error': 'No se enviaron IDs'}, status=400)
        deleted, _ = _contactos_de(user).filter(id__in=ids).delete()
        return JsonResponse({'success': True, 'eliminados': deleted})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
def api_contactos_importar(request):
    user = _get_user(request)
    if not user:
        return JsonResponse({'error': 'No autenticado'}, status=401)
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    try:
        data = json.loads(request.body)
        contactos = data.get('contactos', [])
        resultado = default_message_service.__class__
        from .services import ContactService
        resultado = ContactService.importar_lote(contactos, owner=user)
        return JsonResponse({'success': True, **resultado})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ── Mensajes ──────────────────────────────────────────────────────────────

def api_mensajes_list(request):
    user = _get_user(request)
    if not user:
        return JsonResponse({'error': 'No autenticado'}, status=401)

    page = int(request.GET.get('page', 1))
    per_page = 50
    busqueda = request.GET.get('q', '')
    direccion = request.GET.get('direccion', '')

    qs = _mensajes_de(user).order_by('-sent_at')
    if busqueda:
        qs = qs.filter(Q(phone_number__icontains=busqueda) | Q(content__icontains=busqueda))
    if direccion:
        qs = qs.filter(direction=direccion)

    total = qs.count()
    mensajes = qs[(page - 1) * per_page: page * per_page]

    return JsonResponse({
        'mensajes': [{
            'id': m.id,
            'telefono': m.phone_number,
            'nombre': _contactos_de(user).filter(phone_number=m.phone_number).values_list('full_name', flat=True).first() or m.phone_number,
            'contenido': m.content[:100] if m.content else '',
            'direccion': m.direction,
            'status': m.delivery_status,
            'campana': m.campaign.name if m.campaign else '',
            'fecha': m.sent_at.strftime('%d/%m/%Y %H:%M') if m.sent_at else '',
        } for m in mensajes],
        'total': total,
        'page': page,
        'pages': (total + per_page - 1) // per_page,
    })


@csrf_exempt
@require_http_methods(["POST"])
def api_mensajes_bulk_delete(request):
    user = _get_user(request)
    if not user:
        return JsonResponse({'error': 'No autenticado'}, status=401)
    try:
        data = json.loads(request.body)
        ids = data.get('ids', [])
        if not ids:
            return JsonResponse({'error': 'Sin ids'}, status=400)
        eliminados, _ = _mensajes_de(user).filter(id__in=ids).delete()
        return JsonResponse({'eliminados': eliminados})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
