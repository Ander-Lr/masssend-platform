from django.contrib import admin
from django.contrib.admin.widgets import AdminFileWidget
from django.forms.widgets import Textarea
from django.utils.safestring import mark_safe
from unfold.admin import ModelAdmin
from .models import ApiProvider, Contact, Campaign, Message, CampaignProgress
from .forms import ContactAdminForm
import requests
import threading
from django.conf import settings

# ─── Lock de concurrencia ─────────────────────────────────────────────────────
# CONCEPTO: Concurrencia con hilos
# threading.Lock() garantiza que solo UN hilo a la vez puede lanzar campañas.
# Sin esto, si dos usuarios del admin hacen click en "Ejecutar campaña"
# al mismo tiempo, podrían crearse dos hilos enviando al mismo contacto.
#
# _campaign_locks: diccionario {campaign_id → Lock} para un lock por campaña.
# Así dos campañas DIFERENTES pueden correr en paralelo sin bloquearse entre sí.
import threading
_campaign_locks: dict = {}
_locks_mutex = threading.Lock()  # protege el diccionario de locks

def get_campaign_lock(campaign_id: int) -> threading.Lock:
    """Devuelve (o crea) el Lock para una campaña específica."""
    with _locks_mutex:
        if campaign_id not in _campaign_locks:
            _campaign_locks[campaign_id] = threading.Lock()
        return _campaign_locks[campaign_id]

def _whatsapp_url(path):
    base = getattr(settings, 'WHATSAPP_API_URL', 'http://localhost:3001').rstrip('/')
    return f"{base}{path}"
import time
import base64
import mimetypes
import os
from django.contrib import messages
from django.utils import timezone


@admin.register(ApiProvider)
class ApiProviderAdmin(ModelAdmin):
    list_display = ('business_name', 'display_number', 'phone_number_id', 'is_active', 'created_at')
    search_fields = ('business_name', 'phone_number_id', 'display_number')
    search_help_text = 'Buscar por nombre, número o ID del proveedor'


@admin.register(Contact)
class ContactAdmin(ModelAdmin):
    form = ContactAdminForm
    list_display = ('phone_number_display', 'full_name', 'tags_display', 'estado_display', 'fecha_registro')
    search_fields = ('phone_number', 'full_name', 'tags')
    list_filter = ()
    list_per_page = 50
    change_list_template = 'mass_sender/admin_contact_changelist.html'
    actions = ['limpiar_contactos_invalidos', 'marcar_activo', 'marcar_optout', 'eliminar_contactos_seleccionados']

    def get_actions(self, request):
        actions = super().get_actions(request)
        # Quitar el delete_selected nativo de Django/Unfold que tiene una página de confirmación rota
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

    @admin.action(description='Eliminar contactos seleccionados')
    def eliminar_contactos_seleccionados(self, request, queryset):
        total = queryset.count()
        queryset.delete()
        self.message_user(request, f'✓ {total} contacto(s) eliminado(s) correctamente.', level=messages.SUCCESS)

    def save_model(self, request, obj, form, change):
        if not obj.owner_id:
            obj.owner = request.user
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        qs = super().get_queryset(request).exclude(phone_number__contains='@')
        tag = request.GET.get('_tag')
        if tag:
            qs = qs.filter(tags__icontains=tag)
        return qs

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        # Obtener todas las etiquetas únicas usadas
        all_tags_raw = (
            Contact.objects.exclude(tags__isnull=True).exclude(tags='')
            .values_list('tags', flat=True)
        )
        tags_set = set()
        for t in all_tags_raw:
            for part in t.split(','):
                clean = part.strip()
                if clean:
                    tags_set.add(clean)
        extra_context['available_tags'] = sorted(tags_set)
        extra_context['active_tag'] = request.GET.get('_tag', '')
        extra_context['import_url'] = '/admin/import-contacts/'
        return super().changelist_view(request, extra_context=extra_context)

    @admin.action(description='Eliminar contactos con ID invalido (@lid, @g.us, @newsletter)')
    def limpiar_contactos_invalidos(self, request, queryset):
        total, _ = Contact.objects.filter(phone_number__contains='@').delete()
        self.message_user(request, f'{total} contactos invalidos eliminados.', level=messages.SUCCESS)

    def phone_number_display(self, obj):
        num = obj.phone_number or ''
        return mark_safe(
            f'<span style="display:inline-flex;align-items:center;gap:6px;">'
            f'<img src="https://flagcdn.com/w20/ec.png" width="16" height="11" '
            f'style="border-radius:2px;" alt="EC">'
            f'<span style="font-family:monospace;">+{num}</span>'
            f'</span>'
        )
    phone_number_display.short_description = 'Numero de WhatsApp'

    def tags_display(self, obj):
        if not obj.tags:
            return mark_safe('<span style="color:#d1d5db;font-size:0.8rem;">Sin etiqueta</span>')
        chips = ''
        for t in obj.tags.split(','):
            t = t.strip()
            if t:
                chips += (
                    f'<span style="display:inline-block;background:#f3e8ff;color:#6b21a8;'
                    f'padding:2px 9px;border-radius:20px;font-size:0.73rem;font-weight:600;'
                    f'margin:1px 2px;">{t}</span>'
                )
        return mark_safe(chips) if chips else '—'
    tags_display.short_description = 'Etiquetas'

    def estado_display(self, obj):
        if obj.is_opted_out:
            return mark_safe(
                '<span style="background:#fee2e2;color:#991b1b;padding:3px 10px;'
                'border-radius:999px;font-size:0.73rem;font-weight:700;">Opt-out</span>'
            )
        return mark_safe(
            '<span style="background:#d1fae5;color:#065f46;padding:3px 10px;'
            'border-radius:999px;font-size:0.73rem;font-weight:700;">Activo</span>'
        )
    estado_display.short_description = 'Estado'

    @admin.action(description='Marcar como Activo (puede recibir mensajes)')
    def marcar_activo(self, request, queryset):
        total = queryset.update(is_opted_out=False)
        self.message_user(request, f'{total} contactos marcados como Activo.', level=messages.SUCCESS)

    @admin.action(description='Marcar como Opt-out (no recibirá mensajes)')
    def marcar_optout(self, request, queryset):
        total = queryset.update(is_opted_out=True)
        self.message_user(request, f'{total} contactos marcados como Opt-out.', level=messages.SUCCESS)

    def fecha_registro(self, obj):
        if obj.created_at:
            return obj.created_at.strftime('%d/%m/%Y %H:%M')
        return '—'
    fecha_registro.short_description = 'Fecha de registro'
    fecha_registro.admin_order_field = 'created_at'


# ─────────────────────────────────────────────
# WIDGET PERSONALIZADO: Contador de caracteres
# ─────────────────────────────────────────────
MAX_WPP_CHARS = 4096

class CharCountTextareaWidget(Textarea):
    """
    Textarea con contador de caracteres en tiempo real.
    Limite duro: 4 096 caracteres (límite de WhatsApp).
    Categorias: Corto (<=160), Normal (161-500), Largo (501-1000), Muy largo (1001-4096)
    """

    def render(self, name, value, attrs=None, renderer=None):
        # Inyectar maxlength en los attrs del textarea
        attrs = attrs or {}
        attrs['maxlength'] = MAX_WPP_CHARS
        output = super().render(name, value, attrs, renderer)
        uid = name.replace('-', '_')

        counter_html = mark_safe(f"""
        <div id="ccw_{uid}" style="margin-top:10px; font-family:system-ui,sans-serif;">

            <div style="display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom:7px;">

                <span id="cc_badge_{uid}"
                      style="display:inline-block; padding:3px 12px; border-radius:20px;
                             font-size:0.78rem; font-weight:700; letter-spacing:.02em;
                             background:#d1fae5; color:#065f46; transition:background .25s, color .25s;">
                    Corto
                </span>

                <span id="cc_count_{uid}"
                      style="font-size:0.8rem; color:#6b7280; font-family:monospace; white-space:nowrap;">
                    0 / {MAX_WPP_CHARS:,} caracteres
                </span>
            </div>

            <div style="height:5px; background:#e5e7eb; border-radius:3px; overflow:hidden;">
                <div id="cc_bar_{uid}"
                     style="height:100%; width:0%; border-radius:3px;
                            background:#10b981; transition:width .2s ease, background .25s ease;">
                </div>
            </div>

            <div id="cc_hint_{uid}"
                 style="margin-top:6px; font-size:0.75rem; color:#6b7280; min-height:16px;">
            </div>

        </div>

        <script>
        (function(){{
            var MAX_{uid} = {MAX_WPP_CHARS};

            function initCharCounter_{uid}() {{
                var ta    = document.querySelector('[name="{name}"]');
                var badge = document.getElementById('cc_badge_{uid}');
                var count = document.getElementById('cc_count_{uid}');
                var bar   = document.getElementById('cc_bar_{uid}');
                var hint  = document.getElementById('cc_hint_{uid}');
                if (!ta || !badge) return;

                function update() {{
                    var len = ta.value.length;
                    count.textContent = len.toLocaleString('es') + ' / {MAX_WPP_CHARS:,} caracteres';

                    /* barra: escala 0-MAX, caps al 100% */
                    var pct = Math.min(Math.round(len / MAX_{uid} * 100), 100);
                    bar.style.width = pct + '%';

                    /* Borde rojo si cerca del limite */
                    if (len >= MAX_{uid} - 200) {{
                        ta.style.borderColor = '#ef4444';
                        ta.style.outline = '1px solid #ef4444';
                    }} else {{
                        ta.style.borderColor = '';
                        ta.style.outline = '';
                    }}

                    if (len <= 160) {{
                        badge.textContent        = 'Corto';
                        badge.style.background   = '#d1fae5';
                        badge.style.color        = '#065f46';
                        bar.style.background     = '#10b981';
                        hint.style.color         = '#6b7280';
                        hint.textContent         = 'Ideal para mensajes directos y de alto impacto.';
                    }} else if (len <= 500) {{
                        badge.textContent        = 'Normal';
                        badge.style.background   = '#dbeafe';
                        badge.style.color        = '#1e40af';
                        bar.style.background     = '#3b82f6';
                        hint.style.color         = '#6b7280';
                        hint.textContent         = 'Buen equilibrio entre informacion y brevedad.';
                    }} else if (len <= 1000) {{
                        badge.textContent        = 'Largo';
                        badge.style.background   = '#fef3c7';
                        badge.style.color        = '#92400e';
                        bar.style.background     = '#f59e0b';
                        hint.style.color         = '#92400e';
                        hint.textContent         = 'Considera acortar el mensaje. Mensajes largos pierden atencion en campanas masivas.';
                    }} else if (len < MAX_{uid}) {{
                        badge.textContent        = 'Muy largo';
                        badge.style.background   = '#fee2e2';
                        badge.style.color        = '#991b1b';
                        bar.style.background     = '#ef4444';
                        hint.style.color         = '#991b1b';
                        var restantes = MAX_{uid} - len;
                        hint.textContent         = 'Quedan ' + restantes + ' caracteres. WhatsApp rechaza mensajes de mas de {MAX_WPP_CHARS:,} caracteres.';
                    }} else {{
                        badge.textContent        = 'LIMITE ALCANZADO';
                        badge.style.background   = '#7f1d1d';
                        badge.style.color        = '#fca5a5';
                        bar.style.background     = '#7f1d1d';
                        hint.style.color         = '#dc2626';
                        hint.innerHTML           = '<strong>Limite maximo alcanzado.</strong> El textarea no permite ingresar mas caracteres.';
                    }}
                }}

                ta.addEventListener('input', update);
                update();
            }}

            if (document.readyState === 'loading') {{
                document.addEventListener('DOMContentLoaded', initCharCounter_{uid});
            }} else {{
                initCharCounter_{uid}();
            }}
        }})();
        </script>
        """)

        return mark_safe(str(output) + str(counter_html))


# ─────────────────────────────────────────────
# WIDGET PERSONALIZADO: Zona de carga + Preview
# ─────────────────────────────────────────────
class MediaPreviewWidget(AdminFileWidget):
    """
    Widget con zona drag & drop para imagen/video.
    - Sin archivo: muestra dropzone visual con iconos de imagen y video.
    - Con archivo: muestra preview + botón "Cambiar" y "Eliminar" (auto-guarda al eliminar).
    """

    def render(self, name, value, attrs=None, renderer=None):
        # Obtener la salida nativa de Django (file input + clear checkbox)
        # La ocultamos visualmente pero la mantenemos funcional en el DOM
        django_output = super().render(name, value, attrs, renderer)

        uid = name.replace('-', '_').replace('.', '_')
        clear_name = f'{name}-clear'

        has_file = bool(value and hasattr(value, 'url'))

        # ── SECCIÓN A: Preview del archivo actual (solo si hay archivo) ─────
        current_html = ''
        if has_file:
            url = value.url
            raw = str(value).lower()
            basename = os.path.basename(str(value))
            video_exts = ('.mp4', '.mov', '.avi', '.webm', '.mkv', '.3gpp', '.3gp')
            image_exts = ('.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp')

            if any(raw.endswith(x) for x in video_exts):
                media_tag = f'''
                    <video src="{url}" controls
                           style="max-width:100%;max-height:200px;border-radius:8px;
                                  display:block;background:#000;margin-bottom:10px;">
                    </video>'''
                tipo_label = 'Video adjunto'
            elif any(raw.endswith(x) for x in image_exts):
                media_tag = f'''
                    <img src="{url}" alt="preview"
                         style="max-width:100%;max-height:200px;border-radius:8px;
                                display:block;object-fit:contain;margin-bottom:10px;">'''
                tipo_label = 'Imagen adjunta'
            else:
                media_tag = ''
                tipo_label = 'Archivo adjunto'

            current_html = f'''
            <div id="mw_cur_{uid}"
                 style="padding:16px;background:#faf5ff;border:2px solid #7c3aed;
                        border-radius:12px;max-width:460px;margin-bottom:8px;">
                <p style="font-size:0.70rem;font-weight:700;color:#7c3aed;text-transform:uppercase;
                           letter-spacing:.07em;margin:0 0 10px 0;">{tipo_label}</p>
                {media_tag}
                <p style="font-size:0.76rem;color:#6b7280;margin:0 0 12px 0;
                           font-family:monospace;word-break:break-all;">{basename}</p>
                <div style="display:flex;gap:8px;flex-wrap:wrap;">
                    <button type="button" onclick="mwShowChange_{uid}()"
                            style="padding:6px 16px;background:#fff;color:#7c3aed;
                                   border:1.5px solid #7c3aed;border-radius:7px;
                                   font-size:0.8rem;font-weight:600;cursor:pointer;">
                        Cambiar archivo
                    </button>
                    <button type="button" onclick="mwDelete_{uid}()"
                            style="padding:6px 16px;background:#fff;color:#dc2626;
                                   border:1.5px solid #dc2626;border-radius:7px;
                                   font-size:0.8rem;font-weight:600;cursor:pointer;"
                            onmouseover="this.style.background='#dc2626';this.style.color='#fff';"
                            onmouseout="this.style.background='#fff';this.style.color='#dc2626';">
                        Eliminar archivo
                    </button>
                </div>
            </div>'''

        # ── SECCIÓN B: Drop zone (siempre en el DOM, oculto si hay archivo) ─
        dz_display = 'none' if has_file else 'block'
        dropzone_html = f'''
        <div id="mw_dz_{uid}"
             style="display:{dz_display};border:2px dashed #c4b5fd;border-radius:12px;
                    padding:30px 20px;text-align:center;background:#faf5ff;cursor:pointer;
                    max-width:460px;margin-bottom:8px;
                    transition:border-color .2s,background .2s;"
             onclick="document.getElementById('id_{name}').click()"
             ondragover="event.preventDefault();
                         this.style.borderColor='#7c3aed';
                         this.style.background='#f3e8ff';"
             ondragleave="this.style.borderColor='#c4b5fd';
                          this.style.background='#faf5ff';"
             ondrop="mwHandleDrop_{uid}(event)">

            <!-- Iconos imagen + video -->
            <div style="display:flex;justify-content:center;gap:14px;margin-bottom:14px;">
                <div style="width:56px;height:56px;background:#ede9fe;border-radius:12px;
                            display:flex;align-items:center;justify-content:center;">
                    <svg width="26" height="26" viewBox="0 0 24 24" fill="none"
                         stroke="#7c3aed" stroke-width="1.7" stroke-linecap="round">
                        <rect x="3" y="3" width="18" height="18" rx="2"/>
                        <circle cx="8.5" cy="8.5" r="1.5" fill="#7c3aed" stroke="none"/>
                        <path d="M21 15l-5-5L5 21"/>
                    </svg>
                </div>
                <div style="width:56px;height:56px;background:#ede9fe;border-radius:12px;
                            display:flex;align-items:center;justify-content:center;">
                    <svg width="26" height="26" viewBox="0 0 24 24" fill="none"
                         stroke="#7c3aed" stroke-width="1.7" stroke-linecap="round">
                        <rect x="2" y="4" width="14" height="16" rx="2"/>
                        <path d="M16 8.5l5-3v13l-5-3V8.5z"/>
                    </svg>
                </div>
            </div>

            <p style="font-weight:700;font-size:0.94rem;color:#374151;margin:0 0 4px 0;">
                Arrastra tu imagen o video aquí
            </p>
            <p style="font-size:0.76rem;color:#9ca3af;margin:0 0 16px 0;">
                JPG · PNG · WEBP · MP4 · MOV &nbsp;·&nbsp; Máx. 100 MB para videos
            </p>
            <span style="display:inline-block;padding:8px 22px;background:#7c3aed;color:#fff;
                         border-radius:8px;font-size:0.82rem;font-weight:700;pointer-events:none;">
                Seleccionar archivo
            </span>
        </div>

        <!-- Preview en tiempo real del archivo recién seleccionado -->
        <div id="mw_np_{uid}"
             style="display:none;padding:16px;background:#f0fdf4;border:2px solid #10b981;
                    border-radius:12px;max-width:460px;margin-bottom:8px;">
            <p style="font-size:0.70rem;font-weight:700;color:#065f46;text-transform:uppercase;
                       letter-spacing:.07em;margin:0 0 10px 0;">Listo para guardar</p>
            <img  id="mw_ni_{uid}" style="display:none;max-width:100%;max-height:200px;
                  border-radius:8px;object-fit:contain;margin-bottom:10px;">
            <video id="mw_nv_{uid}" style="display:none;max-width:100%;max-height:200px;
                   border-radius:8px;margin-bottom:10px;" controls></video>
            <p id="mw_nn_{uid}"
               style="font-size:0.76rem;color:#374151;font-family:monospace;
                      margin:0 0 10px 0;word-break:break-all;"></p>
            <button type="button" onclick="mwClearNew_{uid}()"
                    style="padding:6px 14px;background:#fff;color:#6b7280;
                           border:1.5px solid #d1d5db;border-radius:7px;
                           font-size:0.8rem;font-weight:600;cursor:pointer;">
                Cambiar archivo
            </button>
        </div>
        '''

        # ── JS ─────────────────────────────────────────────────────────────
        js = mark_safe(f'''
        <script>
        /* ── Ocultar salida nativa de Django para este campo ── */
        (function() {{
            var wrap = document.getElementById('mw_django_{uid}');
            /* ya está oculto por CSS inline, solo aseguramos */
        }})();

        /* ── Wiring: file input → preview en tiempo real ── */
        (function() {{
            function initMW_{uid}() {{
                var inp = document.getElementById('id_{name}');
                if (!inp) return;
                inp.addEventListener('change', function(e) {{
                    var file = e.target.files[0];
                    if (!file) return;

                    /* Validar tamaño de video */
                    var isVid = /\\.(mp4|mov|avi|webm|mkv|3gp|3gpp)$/i.test(file.name);
                    if (isVid && file.size > 104857600) {{
                        alert('El video pesa ' + (file.size/1048576).toFixed(1) + ' MB. '
                              + 'El límite es 100 MB.\\nPor favor comprime el video o elige uno más pequeño.');
                        e.target.value = '';
                        return;
                    }}

                    /* Mostrar preview */
                    var dz  = document.getElementById('mw_dz_{uid}');
                    var np  = document.getElementById('mw_np_{uid}');
                    var ni  = document.getElementById('mw_ni_{uid}');
                    var nv  = document.getElementById('mw_nv_{uid}');
                    var nn  = document.getElementById('mw_nn_{uid}');
                    var cur = document.getElementById('mw_cur_{uid}');

                    if (dz)  dz.style.display  = 'none';
                    if (cur) cur.style.display  = 'none';
                    np.style.display = 'block';
                    nn.textContent   = file.name + ' (' + (file.size/1048576).toFixed(1) + ' MB)';

                    var reader = new FileReader();
                    reader.onload = function(ev) {{
                        if (file.type.startsWith('image/')) {{
                            ni.src = ev.target.result;
                            ni.style.display = 'block';
                            nv.style.display = 'none';
                        }} else {{
                            nv.src = ev.target.result;
                            nv.style.display = 'block';
                            ni.style.display = 'none';
                        }}
                    }};
                    reader.readAsDataURL(file);
                }});
            }}
            if (document.readyState === 'loading') {{
                document.addEventListener('DOMContentLoaded', initMW_{uid});
            }} else {{
                initMW_{uid}();
            }}
        }})();

        /* ── Soltar archivo en la zona ── */
        function mwHandleDrop_{uid}(e) {{
            e.preventDefault();
            var dz = document.getElementById('mw_dz_{uid}');
            dz.style.borderColor = '#c4b5fd';
            dz.style.background  = '#faf5ff';
            var file = e.dataTransfer.files[0];
            if (!file) return;
            var inp = document.getElementById('id_{name}');
            try {{
                var dt = new DataTransfer();
                dt.items.add(file);
                inp.files = dt.files;
            }} catch(ex) {{ return; }}
            inp.dispatchEvent(new Event('change'));
        }}

        /* ── Limpiar archivo recién seleccionado ── */
        function mwClearNew_{uid}() {{
            document.getElementById('id_{name}').value = '';
            document.getElementById('mw_np_{uid}').style.display  = 'none';
            document.getElementById('mw_ni_{uid}').style.display  = 'none';
            document.getElementById('mw_nv_{uid}').style.display  = 'none';
            var dz  = document.getElementById('mw_dz_{uid}');
            var cur = document.getElementById('mw_cur_{uid}');
            if (dz)  dz.style.display  = 'block';
            if (cur) cur.style.display = 'block';
        }}

        /* ── Mostrar dropzone para cambiar archivo ── */
        function mwShowChange_{uid}() {{
            var cur = document.getElementById('mw_cur_{uid}');
            var dz  = document.getElementById('mw_dz_{uid}');
            if (cur) cur.style.display = 'none';
            if (dz)  dz.style.display  = 'block';
        }}

        /* ── Eliminar archivo existente: guarda el formulario automáticamente ── */
        function mwDelete_{uid}() {{
            if (!confirm('¿Eliminar el archivo adjunto?\\n\\nEl formulario se guardará automáticamente.')) return;

            /* Marcar el checkbox clear de Django */
            var cb = document.querySelector('[name="{clear_name}"]');
            if (cb) cb.checked = true;

            /* Auto-guardar */
            var form = document.querySelector('#content-main form, .change-form form, form[method="post"]');
            if (form) {{
                var saveBtn = form.querySelector('[name="_save"]');
                if (saveBtn) {{ saveBtn.click(); }} else {{ form.submit(); }}
            }}
        }}
        </script>
        ''')

        # Envolver la salida de Django en un div oculto (mantiene el file input + clear checkbox en el DOM)
        hidden_django = mark_safe(
            f'<div id="mw_django_{uid}" style="position:absolute;width:1px;height:1px;'
            f'overflow:hidden;opacity:0;pointer-events:none;">{django_output}</div>'
        )

        return mark_safe(str(hidden_django) + current_html + dropzone_html + str(js))


# ─────────────────────────────────────────────
# CONFIGURACIÓN DE LOTES (ajusta aquí)
# ─────────────────────────────────────────────
BATCH_SIZE             = 50   # mensajes por lote
DELAY_ENTRE_MENSAJES   = 3    # segundos entre cada mensaje dentro del lote
DELAY_ENTRE_LOTES      = 120  # segundos de pausa entre lotes (2 minutos)


# ─────────────────────────────────────────────
# FUNCIÓN DE ENVÍO EN HILO DE FONDO (por lotes)
# ─────────────────────────────────────────────
def _send_campaign_background(campaign_id, contact_ids, cobrado_a=None):
    """
    Corre en un hilo separado.
    Divide los contactos en lotes de BATCH_SIZE, envía cada lote con
    DELAY_ENTRE_MENSAJES segundos entre mensajes y DELAY_ENTRE_LOTES
    segundos de pausa entre lotes para evitar detección de spam por WhatsApp.
    cobrado_a: usuario al que se le cobró la campaña; se le devuelven los
    créditos de los mensajes que el gateway rechazó.
    """
    from django.db import connection
    from mass_sender.models import Campaign, Contact, Message, CampaignProgress

    try:
        campaign = Campaign.objects.get(id=campaign_id)
        contacts = list(Contact.objects.filter(id__in=contact_ids))

        # ─── Respetar la hora programada ───
        if campaign.scheduled_at:
            now = timezone.now()
            if campaign.scheduled_at > now:
                campaign.status = 'scheduled'
                campaign.save()
                print(f"[MassSend] Campana '{campaign.name}' programada para {campaign.scheduled_at}. Esperando...")
                while True:
                    now = timezone.now()
                    if now >= campaign.scheduled_at:
                        break
                    segundos_restantes = (campaign.scheduled_at - now).total_seconds()
                    time.sleep(min(60, segundos_restantes))
                print(f"[MassSend] Hora alcanzada. Iniciando envio de '{campaign.name}'.")

        # ─── Inicializar progreso ───
        progress, _ = CampaignProgress.objects.get_or_create(campaign=campaign)
        progress.total   = len(contact_ids)
        progress.sent    = 0
        progress.failed  = 0
        progress.is_running = True
        progress.last_error = None
        progress.save()

        campaign.status = 'running'
        campaign.save()

        # ─── Preparar media UNA SOLA VEZ ───
        media_payload = {}
        if campaign.media_file and campaign.media_file.name:
            try:
                file_path = campaign.media_file.path
                mimetype, _ = mimetypes.guess_type(file_path)
                if not mimetype:
                    mimetype = 'application/octet-stream'
                with open(file_path, 'rb') as f:
                    file_bytes = f.read()
                media_payload = {
                    'media_base64':   base64.b64encode(file_bytes).decode('utf-8'),
                    'media_mimetype': mimetype,
                    'media_filename': os.path.basename(file_path),
                }
                print(f"[MassSend] Media local: {file_path} ({mimetype}, {len(file_bytes)//1024} KB)")
            except Exception as e:
                progress.last_error = f"Error al leer archivo media: {str(e)[:150]}"
                progress.save()
        elif campaign.media_url:
            from mass_sender.pocketbase_media import descargar_media, es_url_pocketbase
            if es_url_pocketbase(campaign.media_url):
                # Archivo protegido en PocketBase: solo Django (superusuario)
                # puede descargarlo; se envía a Node en base64, igual que un
                # archivo local. Node nunca conoce la URL privada.
                contenido, mime = descargar_media(campaign.media_url)
                if contenido:
                    media_payload = {
                        'media_base64':   base64.b64encode(contenido).decode('utf-8'),
                        'media_mimetype': mime or 'application/octet-stream',
                        'media_filename': campaign.media_url.split('/')[-1],
                    }
                    print(f"[MassSend] Media desde PocketBase (protegido): "
                          f"{campaign.media_url.split('/')[-1]} ({mime}, {len(contenido)//1024} KB)")
                else:
                    progress.last_error = 'No se pudo descargar el media desde PocketBase.'
                    progress.save()
            else:
                media_payload = {'media_url': campaign.media_url}
                print(f"[MassSend] Usando media_url: {campaign.media_url}")

        # ─── Dividir contactos en lotes ───
        lotes = [contacts[i:i + BATCH_SIZE] for i in range(0, len(contacts), BATCH_SIZE)]
        total_lotes = len(lotes)
        print(f"[MassSend] Total contactos: {len(contacts)} | Lotes: {total_lotes} de {BATCH_SIZE} | "
              f"Delay mensajes: {DELAY_ENTRE_MENSAJES}s | Pausa entre lotes: {DELAY_ENTRE_LOTES}s")

        # ─── Enviar lote por lote ───
        for num_lote, lote in enumerate(lotes, start=1):
            print(f"[MassSend] === Lote {num_lote}/{total_lotes} ({len(lote)} contactos) ===")

            for contact in lote:
                nombre        = contact.full_name or "Amigo"
                mensaje_final = campaign.message_template.replace('{{nombre}}', nombre)
                if contact.custom_data:
                    for key, val in contact.custom_data.items():
                        mensaje_final = mensaje_final.replace(f'{{{{{key}}}}}', str(val))

                delivery_status = 'failed'
                wpp_msg_id      = None
                try:
                    payload = {"number": contact.phone_number, "message": mensaje_final, **media_payload}
                    res = requests.post(_whatsapp_url('/api/send'), json=payload, timeout=90)

                    if res.status_code == 200:
                        delivery_status = 'pending'  # Node lo actualizará a 'sent'/'failed' via /api/send-result/
                        progress.sent += 1
                        print(f"[MassSend] Encolado → {contact.phone_number}")
                    elif res.status_code == 422:
                        progress.failed += 1
                        progress.last_error = f"Sin WhatsApp: {contact.phone_number}"
                        print(f"[MassSend] Sin WhatsApp → {contact.phone_number}")
                    else:
                        progress.failed += 1
                        progress.last_error = f"Error {res.status_code} para {contact.phone_number}: {res.text[:80]}"
                        print(f"[MassSend] Error {res.status_code} → {contact.phone_number}")

                except Exception as e:
                    progress.failed += 1
                    progress.last_error = str(e)[:200]
                    print(f"[MassSend] Excepcion → {contact.phone_number}: {e}")

                Message.objects.create(
                    owner_id=campaign.owner_id,
                    campaign=campaign,
                    phone_number=contact.phone_number,
                    content=mensaje_final,
                    direction='outbound',
                    delivery_status=delivery_status,
                    wpp_message_id=wpp_msg_id,
                )
                progress.save()

                # Pausa entre mensajes dentro del mismo lote
                time.sleep(DELAY_ENTRE_MENSAJES)

            # Pausa entre lotes (excepto después del último)
            if num_lote < total_lotes:
                print(f"[MassSend] Lote {num_lote} completado. "
                      f"Esperando {DELAY_ENTRE_LOTES}s antes del siguiente lote...")
                time.sleep(DELAY_ENTRE_LOTES)

        # ─── Finalizar ───
        campaign.status = 'completed'
        campaign.save()
        progress.is_running  = False
        progress.finished_at = timezone.now()
        progress.save()
        if cobrado_a and progress.failed:
            from billing.services import wallet_service
            wallet_service.add_credits(cobrado_a, progress.failed)
        print(f"[MassSend] Campana '{campaign.name}' completada. "
              f"Enviados: {progress.sent} | Fallidos: {progress.failed}")

    except Exception as e:
        print(f"[MassSend] Error critico en campana {campaign_id}: {e}")
        try:
            campaign = Campaign.objects.get(id=campaign_id)
            campaign.status = 'cancelled'
            campaign.save()
            progress = CampaignProgress.objects.filter(campaign=campaign).first()
            if progress:
                progress.is_running  = False
                progress.last_error  = f"Error critico: {str(e)[:200]}"
                progress.finished_at = timezone.now()
                progress.save()
        except Exception:
            pass
    finally:
        connection.close()


# ─────────────────────────────────────────────
# ADMIN: CAMPAÑA
# ─────────────────────────────────────────────
@admin.register(Campaign)
class CampaignAdmin(ModelAdmin):
    list_display = ('name', 'status', 'scheduled_at', 'created_at', 'progreso_display')
    search_fields = ('name',)
    search_help_text = 'Buscar campaña por nombre'
    list_filter = ()
    readonly_fields = ('created_at', 'progreso_info')
    actions = ['execute_campaign_async']

    def save_model(self, request, obj, form, change):
        if not obj.owner_id:
            obj.owner = request.user
        super().save_model(request, obj, form, change)

    fieldsets = (
        ('Información de la Campaña', {
            'fields': ('name', 'status', 'scheduled_at', 'created_at')
        }),
        ('Destinatarios', {
            'fields': ('target_tags',),
            'description': (
                'Deja en blanco para enviar a <strong>todos</strong> los contactos activos. '
                'Escribe una etiqueta (ej: <code>cliente</code>) para enviar solo a los contactos que la tengan. '
                'Puedes ver y gestionar las etiquetas en la lista de Contactos.'
            ),
        }),
        ('Mensaje', {
            'fields': ('message_template',),
            'description': 'Usa {{nombre}} para personalizar con el nombre del contacto.',
        }),
        ('Media (Imagen o Video)', {
            'fields': ('media_file', 'media_url'),
            'description': (
                '<strong>Opcion A — Subir archivo:</strong> Sube una imagen (JPG, PNG, WEBP) o video (MP4) '
                'desde tu computadora. Se guarda en el servidor y se lee directo para enviarlo. <br>'
                '<strong>Opcion B — URL publica:</strong> Pega una URL accesible desde Internet. <br>'
                '<em>Si subes archivo, tiene prioridad sobre la URL.</em>'
            ),
        }),
        ('Progreso de Envio', {
            'fields': ('progreso_info',),
            'classes': ('collapse',),
        }),
    )

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        """Reemplaza widgets: preview para media_file, contador para message_template."""
        if db_field.name == 'media_file':
            kwargs['widget'] = MediaPreviewWidget
        elif db_field.name == 'message_template':
            kwargs['widget'] = CharCountTextareaWidget(attrs={
                'rows': 6,
                'style': 'width:100%; font-size:0.9rem; line-height:1.5; resize:vertical;',
            })
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    def progreso_display(self, obj):
        try:
            p = obj.progress
            if p.is_running:
                pct = int((p.sent + p.failed) / p.total * 100) if p.total else 0
                return f"Enviando {p.sent}/{p.total} ({pct}%)"
            elif p.total > 0:
                return f"{p.sent} enviados / {p.failed} fallidos"
        except CampaignProgress.DoesNotExist:
            pass
        return "—"
    progreso_display.short_description = "Progreso"

    def progreso_info(self, obj):
        try:
            p = obj.progress
            pct = int((p.sent + p.failed) / p.total * 100) if p.total > 0 else 0
            color_bar = '#198754' if not p.is_running else '#4f46e5'
            estado = 'Ejecutandose...' if p.is_running else 'Finalizado'
            html = f"""
            <div style="background:#f8f9fa; border-radius:10px; padding:18px; font-family:system-ui, sans-serif; max-width:500px;">
                <div style="display:flex; align-items:center; gap:8px; margin-bottom:12px;">
                    <span style="font-weight:700; font-size:0.95rem;">{estado}</span>
                </div>
                <div style="display:flex; gap:20px; margin-bottom:12px; font-size:0.88rem;">
                    <span>Total: <strong>{p.total}</strong></span>
                    <span style="color:#198754;">Enviados: <strong>{p.sent}</strong></span>
                    <span style="color:#dc3545;">Fallidos: <strong>{p.failed}</strong></span>
                </div>
                <div style="background:#e9ecef; border-radius:6px; height:14px; margin-bottom:8px; overflow:hidden;">
                    <div style="background:{color_bar}; height:100%; width:{pct}%; border-radius:6px;
                                transition: width 0.5s ease;"></div>
                </div>
                <div style="color:#6c757d; font-size:0.8rem; text-align:right;">{pct}% completado</div>
            """
            if p.last_error:
                html += f'<div style="color:#dc3545; font-size:0.82rem; margin-top:10px; padding:8px; background:#fff3cd; border-radius:6px;"><strong>Ultimo error:</strong><br>{p.last_error}</div>'
            if p.finished_at:
                html += f'<div style="color:#6c757d; font-size:0.78rem; margin-top:8px;">Finalizado: {p.finished_at.strftime("%d/%m/%Y %H:%M:%S")}</div>'
            html += '</div>'
            return mark_safe(html)
        except CampaignProgress.DoesNotExist:
            return mark_safe('<span style="color:#6c757d; font-size:0.85rem;">Sin datos de progreso. Ejecuta la campaña primero.</span>')
    progreso_info.short_description = "Información de Progreso"

    @admin.action(description="Ejecutar campana masiva (en segundo plano)")
    def execute_campaign_async(self, request, queryset):
        from django.http import HttpResponseRedirect

        from .services import destinatarios_campana

        campanas_lanzadas = []

        for campaign in queryset:
            if campaign.status == 'running':
                self.message_user(
                    request,
                    f"La campana '{campaign.name}' ya esta ejecutandose.",
                    level=messages.WARNING
                )
                continue
            if campaign.status == 'completed':
                self.message_user(
                    request,
                    f"La campana '{campaign.name}' ya fue completada. Cambia el estado a Borrador para reenviar.",
                    level=messages.WARNING
                )
                continue

            contacts = list(destinatarios_campana(campaign).values_list('id', flat=True))
            if not contacts:
                self.message_user(
                    request,
                    f"La campana '{campaign.name}' no tiene contactos activos (verifica la etiqueta de filtro).",
                    level=messages.WARNING
                )
                continue

            # ── CONCURRENCIA: verificar con lock antes de lanzar el hilo ──
            # Si dos admins intentan lanzar la misma campaña simultáneamente,
            # el segundo intento no_wait (blocking=False) falla sin bloquearse.
            campaign_lock = get_campaign_lock(campaign.id)
            if not campaign_lock.acquire(blocking=False):
                self.message_user(
                    request,
                    f"La campaña '{campaign.name}' ya está siendo lanzada por otro usuario.",
                    level=messages.WARNING
                )
                continue

            # El hilo libera el lock cuando termina el envío
            def hilo_target(cid, cids, lock):
                try:
                    _send_campaign_background(cid, cids)
                finally:
                    lock.release()  # siempre liberar, incluso si hay error

            hilo = threading.Thread(
                target=hilo_target,
                args=(campaign.id, contacts, campaign_lock),
                daemon=True,
                name=f'Campaign-{campaign.id}'  # nombre descriptivo para debugging
            )
            hilo.start()
            campanas_lanzadas.append((campaign, contacts))

        # Si se lanzo exactamente UNA campana, redirigir al monitor en tiempo real
        if len(campanas_lanzadas) == 1:
            camp = campanas_lanzadas[0][0]
            return HttpResponseRedirect(f'/whatsapp/monitor/{camp.id}/')

        # Si se lanzaron varias, mostrar mensajes normales
        for campaign, contacts in campanas_lanzadas:
            media_info = ""
            if campaign.media_file:
                media_info = f" Con archivo: {os.path.basename(campaign.media_file.name)}."
            elif campaign.media_url:
                media_info = " Con URL adjunta."

            if campaign.scheduled_at and campaign.scheduled_at > timezone.now():
                from django.utils.timezone import localtime
                hora_local = localtime(campaign.scheduled_at).strftime('%d/%m/%Y %H:%M')
                self.message_user(
                    request,
                    f"Campana '{campaign.name}' programada para el {hora_local}.{media_info} "
                    f"El sistema esperara hasta esa hora y enviara a {len(contacts)} contactos.",
                    level=messages.SUCCESS
                )
            else:
                self.message_user(
                    request,
                    f"Campana '{campaign.name}' iniciada para {len(contacts)} contactos.{media_info}",
                    level=messages.SUCCESS
                )


@admin.register(CampaignProgress)
class CampaignProgressAdmin(ModelAdmin):
    list_display = ('campaign', 'total', 'sent', 'failed', 'is_running', 'started_at', 'finished_at')
    list_filter = ('is_running',)
    readonly_fields = ('campaign', 'total', 'sent', 'failed', 'is_running', 'started_at', 'finished_at', 'last_error')


@admin.register(Message)
class MessageAdmin(ModelAdmin):
    list_display = (
        'contacto_display',
        'direccion_display',
        'contenido_preview',
        'estado_display',
        'campaign',
        'sent_at',
    )
    search_fields = ('phone_number', 'content')
    search_help_text = 'Buscar por teléfono o contenido del mensaje'
    list_filter = ()
    readonly_fields = (
        'phone_number', 'direction', 'content', 'delivery_status',
        'campaign', 'sent_at', 'message_type', 'error_log',
    )
    ordering = ('-sent_at',)
    actions = ['marcar_entregado', 'marcar_leido', 'eliminar_lid_invalidos']

    def get_queryset(self, request):
        """Excluir mensajes de @lid del listado."""
        return super().get_queryset(request).exclude(phone_number__contains='@')

    def contacto_display(self, obj):
        num = obj.phone_number or ''
        contacto = Contact.objects.filter(phone_number__icontains=num).first()
        nombre = contacto.full_name if contacto and contacto.full_name else None
        bandera = (
            '<img src="https://flagcdn.com/w20/ec.png" '
            'width="14" height="10" '
            'style="border-radius:2px;margin-right:4px;vertical-align:middle;" '
            'alt="EC">'
        )
        if nombre:
            return mark_safe(
                '<div style="line-height:1.4;">'
                f'<div style="font-weight:700;font-size:0.88rem;">{nombre}</div>'
                f'<div style="color:#888;font-size:0.75rem;font-family:monospace;">'
                f'{bandera}+{num}</div>'
                '</div>'
            )
        return mark_safe(
            f'<span style="font-family:monospace;font-size:0.88rem;">'
            f'{bandera}+{num}</span>'
        )
    contacto_display.short_description = 'Contacto'

    def direccion_display(self, obj):
        if obj.direction == 'inbound':
            return mark_safe(
                '<span style="background:#dbeafe;color:#1d4ed8;'
                'padding:3px 10px;border-radius:999px;'
                'font-size:0.75rem;font-weight:700;">Entrante</span>'
            )
        return mark_safe(
            '<span style="background:#dcfce7;color:#15803d;'
            'padding:3px 10px;border-radius:999px;'
            'font-size:0.75rem;font-weight:700;">Saliente</span>'
        )
    direccion_display.short_description = 'Direccion'

    def contenido_preview(self, obj):
        txt = (obj.content or '').strip()
        return (txt[:60] + '...') if len(txt) > 60 else (txt or '-')
    contenido_preview.short_description = 'Mensaje'

    def estado_display(self, obj):
        STATUS = {
            'pending':   ('#f59e0b', '#fef3c7', 'Pendiente'),
            'sent':      ('#6b7280', '#f3f4f6', 'Enviado'),
            'delivered': ('#3b82f6', '#dbeafe', 'Entregado'),
            'read':      ('#0ea5e9', '#e0f9ff', 'Leido'),
            'failed':    ('#ef4444', '#fee2e2', 'Fallido'),
        }
        color, bg, label = STATUS.get(obj.delivery_status, ('#888', '#f3f4f6', obj.delivery_status))
        return mark_safe(
            f'<span style="background:{bg};color:{color};'
            f'padding:3px 10px;border-radius:999px;'
            f'font-size:0.75rem;font-weight:700;">{label}</span>'
        )
    estado_display.short_description = 'Estado de Entrega'

    @admin.action(description='Marcar seleccionados como Entregado (doble visto gris)')
    def marcar_entregado(self, request, queryset):
        total = queryset.filter(direction='outbound').update(delivery_status='delivered')
        self.message_user(request, f'{total} mensajes marcados como Entregado.', level=messages.SUCCESS)

    @admin.action(description='Marcar seleccionados como Leido (doble visto azul)')
    def marcar_leido(self, request, queryset):
        total = queryset.filter(direction='outbound').update(delivery_status='read')
        self.message_user(request, f'{total} mensajes marcados como Leido.', level=messages.SUCCESS)

    @admin.action(description='Eliminar mensajes con ID invalido (@lid)')
    def eliminar_lid_invalidos(self, request, queryset):
        total, _ = Message.objects.filter(phone_number__contains='@').delete()
        self.message_user(
            request,
            f'{total} mensajes con ID invalido eliminados.',
            level=messages.SUCCESS
        )
