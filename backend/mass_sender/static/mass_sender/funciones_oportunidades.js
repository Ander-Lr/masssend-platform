// ── Configuración de etapas ──
const OPORT_STAGES = [
    { key: 'nuevo',        label: 'Nuevo',        color: '#2D9E7A' },
    { key: 'contactado',   label: 'Contactado',   color: '#4A7FD4' },
    { key: 'propuesta',    label: 'Propuesta',    color: '#F5A623' },
    { key: 'negociacion',  label: 'Negociación',  color: '#E8832A' },
    { key: 'ganado',       label: 'Ganado',       color: '#27AE60' },
    { key: 'perdido',      label: 'Perdido',      color: '#E74C3C' },
];

// ── Estado local (se reemplazará con fetch al backend) ──
let oportData = [
    { id: 1, titulo: 'Renovación contrato', contacto: '593964183445', contacto_nombre: 'Jennifer Guerra', stage: 'nuevo',        vendedor: 'Ana Martínez',  notas: 'Interesada en plan anual.',          fecha: '2026-02-19' },
    { id: 2, titulo: 'Propuesta servicios', contacto: '593991234567', contacto_nombre: 'Carlos R.',        stage: 'propuesta',    vendedor: 'Carlos López',  notas: 'Enviar cotización este viernes.',    fecha: '2026-02-18' },
    { id: 3, titulo: 'Cierre pendiente',    contacto: '593987654321', contacto_nombre: 'María Torres',      stage: 'negociacion',  vendedor: 'Ana Martínez',  notas: 'Esperando aprobación gerencia.',    fecha: '2026-02-17' },
    { id: 4, titulo: 'Demo agendada',       contacto: '593911111111', contacto_nombre: '+593 91 111 1111',  stage: 'contactado',   vendedor: 'María Torres',  notas: '',                                   fecha: '2026-02-16' },
];

let oportVistaActual = 'kanban';
let oportEditandoId  = null;

let oportInicializado = false;

function oportInit() {
    if (oportInicializado) {
        oportRenderAll();
        return;
    }
    oportInicializado = true;
    oportConstruirKanban();
    oportPoblarFiltroVendedores();
    oportRenderAll();
}

// ── Construir columnas kanban ──
function oportConstruirKanban() {
    const wrapper = document.getElementById('oport-vista-kanban');
    wrapper.innerHTML = '';
    OPORT_STAGES.forEach(s => {
        wrapper.insertAdjacentHTML('beforeend', `
            <div class="oport-kanban-col" id="oport-col-${s.key}">
                <div class="oport-col-header">
                    <div class="oport-col-title">
                        <div class="oport-stage-dot" style="background:${s.color};"></div>
                        ${s.label}
                    </div>
                    <span class="oport-col-count" id="oport-cnt-${s.key}">0</span>
                </div>
                <div id="oport-cards-${s.key}"></div>
                <button class="oport-btn-add" onclick="oportAbrirPanel('${s.key}')">
                    <svg width="11" height="11" viewBox="0 0 24 24" fill="none"
                         stroke="currentColor" stroke-width="2.5">
                        <line x1="12" y1="5" x2="12" y2="19"/>
                        <line x1="5" y1="12" x2="19" y2="12"/>
                    </svg>
                    Agregar
                </button>
            </div>
        `);
    });
}

// ── Renderizar todo ──
function oportRenderAll() {
    const texto    = (document.getElementById('oport-filtro-texto')?.value || '').toLowerCase();
    const vendedor = document.getElementById('oport-filtro-vendedor')?.value || '';
    const stage    = document.getElementById('oport-filtro-stage')?.value || '';

    const filtered = oportData.filter(o => {
        const matchTexto    = !texto    || o.titulo.toLowerCase().includes(texto) || (o.contacto_nombre||'').toLowerCase().includes(texto);
        const matchVendedor = !vendedor || o.vendedor === vendedor;
        const matchStage    = !stage    || o.stage === stage;
        return matchTexto && matchVendedor && matchStage;
    });

    // Update total badge
    document.getElementById('oport-total-badge').textContent = filtered.length;

    if (oportVistaActual === 'kanban') {
        oportRenderKanban(filtered);
    } else {
        oportRenderLista(filtered);
    }
}

// ── Render kanban ──
function oportRenderKanban(data) {
    OPORT_STAGES.forEach(s => {
        const container = document.getElementById(`oport-cards-${s.key}`);
        const cnt       = document.getElementById(`oport-cnt-${s.key}`);
        if (!container) return;
        const items = data.filter(o => o.stage === s.key);
        cnt.textContent = items.length;

        if (items.length === 0) {
            container.innerHTML = `
                <div class="oport-empty">
                    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <rect x="3" y="3" width="18" height="18" rx="2"/>
                        <line x1="9" y1="9" x2="15" y2="9"/>
                        <line x1="9" y1="13" x2="12" y2="13"/>
                    </svg>
                    <div>Sin oportunidades</div>
                </div>`;
            return;
        }

        container.innerHTML = items.map(o => `
            <div class="oport-card" onclick="oportAbrirPanel(null, ${o.id})">
                <div class="oport-card-title">${o.titulo}</div>
                <div class="oport-card-contact">
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none"
                         stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="7" r="4"/>
                        <path d="M4 21c0-4 4-7 8-7s8 3 8 7"/>
                    </svg>
                    ${o.contacto_nombre || o.contacto}
                </div>
                <div class="oport-card-footer">
                    <span class="oport-badge-vendedor">${o.vendedor || 'Sin asignar'}</span>
                    <span class="oport-card-date">${o.fecha || ''}</span>
                </div>
                ${o.notas ? `<div class="oport-card-notes">${o.notas}</div>` : ''}
            </div>
        `).join('');
    });
}

// ── Render lista ──
function oportRenderLista(data) {
    const tbody = document.getElementById('oport-tabla-body');
    if (data.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" style="text-align:center; padding:32px;
                    color: var(--bs-secondary-color); font-size:0.8rem;">
                    No hay oportunidades
                </td>
            </tr>`;
        return;
    }
    tbody.innerHTML = data.map(o => {
        const stageInfo = OPORT_STAGES.find(s => s.key === o.stage) || OPORT_STAGES[0];
        return `
            <tr style="cursor:pointer;" onclick="oportAbrirPanel(null, ${o.id})">
                <td style="font-weight:600;">${o.titulo}</td>
                <td style="color:var(--bs-secondary-color);">${o.contacto_nombre || o.contacto}</td>
                <td>
                    <span style="font-size:0.68rem; font-weight:700; padding:3px 10px;
                                 border-radius:20px;
                                 background:${stageInfo.color}22;
                                 color:${stageInfo.color};">
                        ${stageInfo.label}
                    </span>
                </td>
                <td>${o.vendedor || '<span style="color:var(--bs-secondary-color)">Sin asignar</span>'}</td>
                <td style="color:var(--bs-secondary-color);">${o.fecha || ''}</td>
                <td>
                    <button class="btn btn-sm border-0 p-1"
                            style="color:var(--bs-secondary-color);"
                            onclick="event.stopPropagation(); oportEliminar(${o.id})"
                            title="Eliminar">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                            <path d="M2.75 6.17C2.75 5.7 3.1 5.33 3.52 5.33H6.19L7.36 3.95C7.68 3.56 8.18 3.33 8.7 3.33H15.3C15.82 3.33 16.32 3.56 16.64 3.95L17.81 5.33H20.48C20.9 5.33 21.25 5.7 21.25 6.17C21.25 6.63 20.9 7 20.48 7H3.52C3.1 7 2.75 6.63 2.75 6.17Z"/>
                            <path opacity=".5" d="M11.61 22H12.39C15.1 22 16.45 22 17.34 21.14C18.22 20.27 18.31 18.86 18.49 16.03L18.75 11.95C18.84 10.41 18.89 9.64 18.45 9.15C18.01 8.67 17.26 8.67 15.77 8.67H8.23C6.74 8.67 5.99 8.67 5.55 9.15C5.11 9.64 5.16 10.41 5.26 11.95L5.52 16.03C5.7 18.86 5.79 20.27 6.67 21.14C7.55 22 8.9 22 11.61 22Z"/>
                        </svg>
                    </button>
                </td>
            </tr>`;
    }).join('');
}

// ── Poblar select vendedores ──
function oportPoblarFiltroVendedores() {
    const vendedores = [...new Set(oportData.map(o => o.vendedor).filter(Boolean))];
    const selFiltro  = document.getElementById('oport-filtro-vendedor');
    const selPanel   = document.getElementById('oport-input-vendedor');
    vendedores.forEach(v => {
        if (selFiltro) selFiltro.insertAdjacentHTML('beforeend', `<option value="${v}">${v}</option>`);
        if (selPanel)  selPanel.insertAdjacentHTML('beforeend',  `<option value="${v}">${v}</option>`);
    });
}

// ── Filtrar ──
function oportFiltrar() { oportRenderAll(); }

// ── Toggle vista ──
function oportSetVista(vista) {
    oportVistaActual = vista;
    const kanbanEl = document.getElementById('oport-vista-kanban');
    const listaEl  = document.getElementById('oport-vista-lista');
    const btnK     = document.getElementById('oport-btn-kanban');
    const btnL     = document.getElementById('oport-btn-lista');

    if (vista === 'kanban') {
        kanbanEl.style.display = 'flex';
        listaEl.style.display  = 'none';
        btnK.style.background  = '#fff';
        btnK.style.color       = 'var(--bs-primary)';
        btnK.style.boxShadow   = '0 1px 4px rgba(0,0,0,0.08)';
        btnL.style.background  = 'transparent';
        btnL.style.color       = 'var(--bs-secondary-color)';
        btnL.style.boxShadow   = 'none';
    } else {
        kanbanEl.style.display = 'none';
        listaEl.style.display  = 'block';
        btnL.style.background  = '#fff';
        btnL.style.color       = 'var(--bs-primary)';
        btnL.style.boxShadow   = '0 1px 4px rgba(0,0,0,0.08)';
        btnK.style.background  = 'transparent';
        btnK.style.color       = 'var(--bs-secondary-color)';
        btnK.style.boxShadow   = 'none';
    }
    oportRenderAll();
}

// ── Abrir panel nuevo/editar ──
function oportAbrirPanel(stagePreset = null, id = null) {
    oportEditandoId = id;
    const titulo = document.getElementById('oport-panel-titulo');
    titulo.textContent = id ? 'Editar oportunidad' : 'Nueva oportunidad';

    // Renderizar stage pills
    const pillsContainer = document.getElementById('oport-stage-pills');
    pillsContainer.innerHTML = OPORT_STAGES.map(s => `
        <button type="button"
                class="oport-stage-pill ${(stagePreset === s.key || (!stagePreset && !id && s.key === 'nuevo')) ? 'selected' : ''}"
                data-stage="${s.key}"
                onclick="oportSeleccionarStage('${s.key}')">
            ${s.label}
        </button>
    `).join('');

    // Rellenar si edición
    if (id) {
        const o = oportData.find(x => x.id === id);
        if (o) {
            document.getElementById('oport-input-titulo').value    = o.titulo;
            let contactVal = o.contacto || '';
            if (contactVal.startsWith('593')) {
                contactVal = contactVal.substring(3);
            }
            document.getElementById('oport-input-contacto').value  = contactVal;
            document.getElementById('oport-input-notas').value     = o.notas || '';
            document.getElementById('oport-input-stage').value     = o.stage;
            document.getElementById('oport-input-vendedor').value  = o.vendedor || '';
            // Marcar pill activa
            pillsContainer.querySelectorAll('.oport-stage-pill').forEach(p => {
                p.classList.toggle('selected', p.dataset.stage === o.stage);
            });
        }
    } else {
        document.getElementById('oport-input-titulo').value    = '';
        document.getElementById('oport-input-contacto').value  = '';
        document.getElementById('oport-input-notas').value     = '';
        document.getElementById('oport-input-stage').value     = stagePreset || 'nuevo';
        document.getElementById('oport-input-vendedor').value  = '';
    }

    document.getElementById('panelOportunidad').style.display = 'block';
    setTimeout(() => document.getElementById('oport-input-titulo').focus(), 50);
}

function oportSeleccionarStage(key) {
    document.getElementById('oport-input-stage').value = key;
    document.querySelectorAll('.oport-stage-pill').forEach(p => {
        p.classList.toggle('selected', p.dataset.stage === key);
    });
}

function oportCerrarPanel() {
    document.getElementById('panelOportunidad').style.display = 'none';
    oportEditandoId = null;
}

// ── Guardar ──
function oportGuardar() {
    const titulo   = document.getElementById('oport-input-titulo').value.trim();
    let contacto = document.getElementById('oport-input-contacto').value.trim();
    if (contacto && !contacto.startsWith('593')) {
        contacto = '593' + contacto;
    }
    const stage    = document.getElementById('oport-input-stage').value;
    const vendedor = document.getElementById('oport-input-vendedor').value;
    const notas    = document.getElementById('oport-input-notas').value.trim();

    if (!titulo) {
        document.getElementById('oport-input-titulo').style.borderColor = '#dc3545';
        document.getElementById('oport-input-titulo').focus();
        return;
    }

    const btn = document.getElementById('oport-btn-guardar');
    btn.disabled     = true;
    btn.textContent  = 'Guardando...';

    // ── Aquí irá el fetch al backend ──
    // fetch('guardar_oportunidad.php', { method:'POST', ... })
    // Por ahora simulamos localmente:
    setTimeout(() => {
        if (oportEditandoId) {
            const idx = oportData.findIndex(o => o.id === oportEditandoId);
            if (idx !== -1) {
                oportData[idx] = { ...oportData[idx], titulo, contacto, stage, vendedor, notas };
            }
        } else {
            oportData.push({
                id: Date.now(),
                titulo, contacto,
                contacto_nombre: contacto,
                stage, vendedor, notas,
                fecha: new Date().toISOString().split('T')[0]
            });
        }

        btn.disabled    = false;
        btn.textContent = 'Guardar';
        oportCerrarPanel();
        oportRenderAll();
    }, 300);
}

// ── Eliminar ──
function oportEliminar(id) {
    if (!confirm('¿Eliminar esta oportunidad?')) return;
    oportData = oportData.filter(o => o.id !== id);
    oportRenderAll();
}

// ── Auto-inicializar cuando el elemento esté visible ──
document.addEventListener('DOMContentLoaded', () => {
    oportInit();
});