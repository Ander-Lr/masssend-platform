// ===============================================
// VARIABLES GLOBALES
// ===============================================
let chatActivo = {
    numero: null,
    nombre: null
};

let todasLasConversaciones = {};
let ultimoTimestamp = 0;
let pollingActivo = false;

function formatearNumero(numero) {
    const n = String(numero).replace(/\D/g, '');
    // Ecuador: 593 XX XXX XXXX (12 dígitos con código de país)
    if (n.startsWith('593') && n.length >= 12) {
        return '🇪🇨 +593 ' + n.substring(3, 5) + ' ' + n.substring(5, 8) + ' ' + n.substring(8);
    }
    if (n.length >= 11) {
        return '+' + n.substring(0, 3) + ' ' + n.substring(3, 5) + ' ' + n.substring(5, 8) + ' ' + n.substring(8);
    }
    return '+' + n;
}

// ===============================================
// POLLING INTELIGENTE (Solo actualiza si hay cambios)
// ===============================================
function iniciarPolling() {
    if (pollingActivo) return;
    pollingActivo = true;

    function poll() {
        fetch(`leer_mensajes.php?last_update=${ultimoTimestamp}&t=${Date.now()}`)
            .then(response => response.json())
            .then(data => {
                if (data.has_changes) {
                    // 🎯 PRESERVAR SCROLL
                    const chatMessages = document.querySelector('.chat-messages');
                    const scrollAntes = chatMessages ? chatMessages.scrollTop : 0;
                    const scrollMax = chatMessages ? chatMessages.scrollHeight : 0;
                    const estaAbajo = chatMessages ?
                        (scrollMax - scrollAntes - chatMessages.clientHeight) < 50 : true;

                    // ✅ GUARDAR conversación actual ANTES de actualizar
                    const conversacionAnterior = chatActivo.numero ?
                        JSON.stringify(todasLasConversaciones[chatActivo.numero]?.mensajes || []) : null;

                    ultimoTimestamp = data.timestamp;
                    todasLasConversaciones = data.mensajes;

                    actualizarListaChats();

                    if (chatActivo.numero) {
                        //  SOLO refrescar si HAY MENSAJES NUEVOS en este chat
                        const conversacionNueva = JSON.stringify(todasLasConversaciones[chatActivo.numero]?.mensajes || []);

                        if (conversacionAnterior !== conversacionNueva) {
                            // HAY CAMBIOS → Refrescar mensajes
                            mostrarMensajes(chatActivo.numero);

                            // Solo auto-scroll si estaba al final
                            setTimeout(() => {
                                if (chatMessages) {
                                    if (estaAbajo) {
                                        chatMessages.scrollTop = chatMessages.scrollHeight;
                                    } else {
                                        chatMessages.scrollTop = scrollAntes;
                                    }
                                }
                            }, 50);
                        }
                        // Si NO hay cambios, NO hacer nada (evita parpadeo)
                    } else {
                        // Si no hay chat activo, abrir el primero
                        const primeraConversacion = Object.keys(todasLasConversaciones)[0];
                        if (primeraConversacion) {
                            abrirChat(primeraConversacion);
                        }
                    }
                } else {
                    // No hay cambios, solo actualizar timestamp
                    ultimoTimestamp = data.timestamp;
                }

                // Siguiente poll después de 3 segundos
                if (pollingActivo) {
                    setTimeout(poll, 3000);
                }
            })
            .catch(error => {
                console.error('Error en polling:', error);
                if (pollingActivo) {
                    setTimeout(poll, 5000);
                }
            });
    }

    poll();
}

function detenerPolling() {
    pollingActivo = false;
}

function actualizarListaChats() {
    const chatList = document.querySelector('.chat-list');
    if (!chatList) return;

    chatList.innerHTML = '';

    for (let numero in todasLasConversaciones) {
        const conv = todasLasConversaciones[numero];
        const ultimoMensaje = conv.mensajes[conv.mensajes.length - 1];

        if (!ultimoMensaje) continue;

        const noLeidos = conv.unread_count || 0;
        const tieneNoLeidos = noLeidos > 0;

        let textoPreview = ultimoMensaje.texto.substring(0, 30);
        if (ultimoMensaje.texto.length > 30) textoPreview += '...';

        let previewPrefix = '';
        if (ultimoMensaje.tipo === 'enviado') {
            previewPrefix = obtenerIconoEstado(ultimoMensaje.status);
        }

        const yaGuardado = !!(conv.custom_name || conv.wa_name);

        const chatHTML = `
            <div class="chat-item-wrapper">
                <a href="#" class="list-group-item list-group-item-action d-flex justify-content-between align-items-start chat-item ${tieneNoLeidos ? 'chat-no-leido' : ''}" data-numero="${numero}">
                    <div class="d-flex align-items-center">
                        <span class="me-2">
                            <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" fill="none" viewBox="0 0 24 24">
                                <circle cx="12" cy="7" r="4" stroke="#2D2A4A" stroke-width="2" />
                                <path d="M4 21c0-4 4-7 8-7s8 3 8 7" stroke="#2D2A4A" stroke-width="2" />
                            </svg>
                        </span>
                        <div>
                            <h7 class="mb-0 fw-bold">${conv.custom_name || formatearNumero(numero)}</h7> <br>
                            <small class="${tieneNoLeidos ? 'text-dark fw-semibold' : 'text-muted'}">${previewPrefix}${textoPreview}</small>
                        </div>
                    </div>
                    <div class="text-end d-flex flex-column align-items-end">
                        <small class="${tieneNoLeidos ? 'fw-bold text-primary' : 'text-muted'}">${ultimoMensaje.hora}</small>
                        ${tieneNoLeidos ? `<span class="badge rounded-circle bg-primary text-white mt-1 me-2" style="width:20px;height:20px;font-size:11px;display:flex;align-items:center;justify-content:center;">${noLeidos}</span>` : ''}
                    </div>
                </a>

                <!-- 3 puntos -->
                <div class="chat-menu-btn" data-numero="${numero}">
                    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="currentColor" viewBox="0 0 16 16">
                        <circle cx="8" cy="2" r="1.5"/><circle cx="8" cy="8" r="1.5"/><circle cx="8" cy="14" r="1.5"/>
                    </svg>
                </div>

                <!-- Dropdown -->
                <div class="chat-dropdown d-none" data-numero="${numero}">
                    <div class="chat-dropdown-item" data-action="${yaGuardado ? 'editar' : 'guardar'}" data-numero="${numero}">
                        <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                        </svg>
                        ${yaGuardado ? 'Editar contacto' : 'Guardar contacto'}
                    </div>
                    ${yaGuardado ? `
                    <div class="chat-dropdown-item chat-dropdown-item-danger" data-action="eliminar" data-numero="${numero}">
                        <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="currentColor">
                            <path d="M2.75 6.17C2.75 5.7 3.1 5.33 3.52 5.33H6.19L7.36 3.95C7.68 3.56 8.18 3.33 8.7 3.33H15.3C15.82 3.33 16.32 3.56 16.64 3.95L17.81 5.33H20.48C20.9 5.33 21.25 5.7 21.25 6.17C21.25 6.63 20.9 7 20.48 7H3.52C3.1 7 2.75 6.63 2.75 6.17Z"/>
                            <path opacity=".5" d="M11.61 22H12.39C15.1 22 16.45 22 17.34 21.14C18.22 20.27 18.31 18.86 18.49 16.03L18.75 11.95C18.84 10.41 18.89 9.64 18.45 9.15C18.01 8.67 17.26 8.67 15.77 8.67H8.23C6.74 8.67 5.99 8.67 5.55 9.15C5.11 9.64 5.16 10.41 5.26 11.95L5.52 16.03C5.7 18.86 5.79 20.27 6.67 21.14C7.55 22 8.9 22 11.61 22Z"/>
                        </svg>
                        Eliminar contacto
                    </div>` : ''}
                </div>
            </div>
        `;

        chatList.insertAdjacentHTML('beforeend', chatHTML);
    }

    // Click en chat
    document.querySelectorAll('.chat-item').forEach(item => {
        item.addEventListener('click', function (e) {
            e.preventDefault();
            const numero = this.dataset.numero;
            marcarComoLeido(numero);
            abrirChat(numero);
        });
    });

    // Click en 3 puntos
    document.querySelectorAll('.chat-menu-btn').forEach(btn => {
        btn.addEventListener('click', function (e) {
            e.stopPropagation();
            const numero = this.dataset.numero;
            const dropdown = document.querySelector(`.chat-dropdown[data-numero="${numero}"]`);
            document.querySelectorAll('.chat-dropdown').forEach(d => {
                if (d !== dropdown) d.classList.add('d-none');
            });
            dropdown.classList.toggle('d-none');
        });
    });

    // Click en opción del dropdown
    document.querySelectorAll('.chat-dropdown-item').forEach(item => {
        item.addEventListener('click', function (e) {
            e.stopPropagation();
            const accion = this.dataset.action;
            const numero = this.dataset.numero;
            document.querySelectorAll('.chat-dropdown').forEach(d => d.classList.add('d-none'));

            if (accion === 'guardar' || accion === 'editar') {
                abrirModalContacto(numero);
            } else if (accion === 'eliminar') {
                eliminarContacto(numero);
            }
        });
    });

    // Cerrar dropdown al click fuera
    document.addEventListener('click', () => {
        document.querySelectorAll('.chat-dropdown').forEach(d => d.classList.add('d-none'));
    });
}

function abrirModalContacto(numero) {
    const conv = todasLasConversaciones[numero];
    const nombreActual = conv.custom_name || conv.wa_name || '';
    const titulo = nombreActual ? 'Editar contacto' : 'Guardar contacto';

    // Eliminar panel anterior si existe
    const panelExistente = document.getElementById('panelContacto');
    if (panelExistente) panelExistente.remove();

    document.body.insertAdjacentHTML('beforeend', `
        <div id="panelContacto" style="display:block;position:fixed;inset:0;z-index:9999;">

            <!-- Fondo -->
            <div onclick="cerrarPanelContacto()" 
                 style="position:absolute;inset:0;background:rgba(255,255,255,0.5);"></div>

            <!-- Panel -->
            <div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);
                        width:90%;max-width:400px;
                        background:var(--bs-body-bg);color:var(--bs-body-color);
                        border-radius:16px;overflow:hidden;display:flex;flex-direction:column;
                        box-shadow:0 20px 60px rgba(0,0,0,.3);">

                <!-- Header -->
                <div style="padding:16px 20px;display:flex;align-items:center;gap:12px;
                            background:var(--bs-primary);
                            border-bottom:1px solid var(--bs-border-color);">
                    <button onclick="cerrarPanelContacto()" class="btn btn-link p-0" style="color:inherit;">
                        <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
                            <path d="M18 6L6 18M6 6L18 18" stroke="#fff" stroke-width="2" stroke-linecap="round"/>
                        </svg>
                    </button>
                    <h6 class="mb-0 fw-bold text-white" style="font-size:.95rem;">${titulo}</h6>
                </div>

                <!-- Contenido -->
                <div style="padding:20px;display:flex;flex-direction:column;gap:16px;">

                    <div>
                        <label style="font-size:0.82rem;color:var(--bs-secondary-color);margin-bottom:6px;display:block;">
                            Nombre del contacto
                        </label>
                        <input type="text" 
                               id="panelContactoNombre" 
                               class="form-control"
                               placeholder="Ej: Juan Cliente"
                               value="${nombreActual}"
                               style="border:1.5px solid var(--bs-border-color);border-radius:10px;padding:10px 14px;font-size:0.9rem;"
                               onkeydown="if(event.key==='Enter') guardarContacto('${numero}')">
                    </div>

                    <div style="display:flex;gap:10px;justify-content:flex-end;">
                        <button onclick="cerrarPanelContacto()" 
                                class="btn btn-sm"
                                style="border-radius:8px;padding:8px 18px;border:1px solid var(--bs-border-color);">
                            Cancelar
                        </button>
                        <button onclick="guardarContacto('${numero}')" 
                                id="panelContactoBtn"
                                class="btn btn-sm btn-primary"
                                style="border-radius:8px;padding:8px 18px;">
                            Guardar
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `);

    // Focus al input
    setTimeout(() => {
        const input = document.getElementById('panelContactoNombre');
        if (input) {
            input.focus();
            input.select();
            input.addEventListener('focus', function() {
                this.style.borderColor = 'var(--bs-primary)';
                this.style.boxShadow = '0 0 0 3px rgba(var(--bs-primary-rgb), 0.15)';
            });
            input.addEventListener('blur', function() {
                this.style.borderColor = 'var(--bs-border-color)';
                this.style.boxShadow = 'none';
            });
        }
    }, 50);
}

function cerrarPanelContacto() {
    const panel = document.getElementById('panelContacto');
    if (panel) panel.remove();
}

function guardarContacto(numero) {
    const nombre = document.getElementById('panelContactoNombre').value.trim();
    if (!nombre) {
        const input = document.getElementById('panelContactoNombre');
        input.style.borderColor = '#dc3545';
        input.style.boxShadow = '0 0 0 3px rgba(220,53,69,0.15)';
        input.placeholder = 'El nombre no puede estar vacío';
        input.focus();
        return;
    }

    const btn = document.getElementById('panelContactoBtn');
    btn.disabled = true;
    btn.textContent = 'Guardando...';

    fetch('guardar_contacto.php', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone_number: numero, custom_name: nombre })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            todasLasConversaciones[numero].custom_name = nombre;
            todasLasConversaciones[numero].nombre = nombre;
            cerrarPanelContacto();
            actualizarListaChats();
        } else {
            alert('Error: ' + (data.error || 'intenta de nuevo'));
            btn.disabled = false;
            btn.textContent = 'Guardar';
        }
    })
    .catch(() => {
        alert('Error de conexión');
        btn.disabled = false;
        btn.textContent = 'Guardar';
    });
}

function eliminarContacto(numero) {
    const modal = document.getElementById('modalEliminarContacto');
    modal.style.display = 'block';

    document.getElementById('btnConfirmarEliminarContacto').onclick = () => {
        ejecutarEliminarContacto(numero);
    };
}

function cerrarModalEliminarContacto() {
    document.getElementById('modalEliminarContacto').style.display = 'none';
}

function ejecutarEliminarContacto(numero) {
    const btn = document.getElementById('btnConfirmarEliminarContacto');
    btn.disabled    = true;
    btn.textContent = 'Eliminando...';

    fetch('eliminar_contacto.php', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone_number: numero })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            todasLasConversaciones[numero].custom_name = null;
            todasLasConversaciones[numero].wa_name     = null;
            todasLasConversaciones[numero].nombre      = formatearNumero(numero);
            cerrarModalEliminarContacto();
            actualizarListaChats();
            if (chatActivo.numero === numero) {
                chatActivo.nombre = formatearNumero(numero);
                const h = document.querySelector('#colChat h6');
                if (h) h.textContent = formatearNumero(numero);
                actualizarPanelInfo(numero);
            }
        } else {
            alert('Error: ' + (data.error || 'intenta de nuevo'));
        }
    })
    .catch(() => alert('Error de conexión'))
    .finally(() => {
        btn.disabled    = false;
        btn.textContent = 'Sí, eliminar';
    });
}

// ============================================
// MARCAR COMO LEÍDO 
// ============================================
function marcarComoLeido(numero) {
    const conv = todasLasConversaciones[numero];
    if (!conv || conv.unread_count === 0) return;

    // Actualizar localmente para respuesta inmediata
    conv.unread_count = 0;
    conv.mensajes.forEach(msg => { msg.is_read = 1; });
    actualizarListaChats();

    // Guardar en BD (UPDATE is_read = 1 en los mensajes inbound)
    fetch('marcar_leido.php', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone_number: numero })
    }).catch(err => console.error('Error marcando como leído:', err));
}

function mostrarChat() {
    const esLayoutSingle = window.innerWidth < 1200;
    const colConversaciones = document.getElementById('colConversaciones');
    const colChat = document.getElementById('colChat');
    const welcomeScreen = document.getElementById('welcomeScreen');
    const colInfo = document.getElementById('colInfo');

    // Siempre cerramos el panel de info al cambiar de chat por seguridad
    if (colInfo) {
        colInfo.classList.add('d-none');
        colInfo.style.setProperty('display', 'none', 'important');
    }

    if (esLayoutSingle) {
        if (colConversaciones) colConversaciones.style.setProperty('display', 'none', 'important');
        if (colChat) colChat.style.setProperty('display', 'block', 'important');
    } else {
        if (colConversaciones) colConversaciones.style.setProperty('display', 'block', 'important');
        if (welcomeScreen) welcomeScreen.style.setProperty('display', 'none', 'important');
        if (colChat) colChat.style.setProperty('display', 'block', 'important');
    }
}

function mostrarWelcomeScreen() {
    const welcomeScreen = document.getElementById('welcomeScreen');
    const colChat = document.getElementById('colChat');
    
    if (welcomeScreen) {
        welcomeScreen.style.setProperty('display', 'block', 'important');
    }
    if (colChat) {
        colChat.style.setProperty('display', 'none', 'important');
    }
}

// ===============================================
// ABRIR CHAT
// ===============================================
function actualizarPanelInfo(numero) {
    const conv = todasLasConversaciones[numero];
    if (!conv) return;

    // h6 → nombre de Meta (wa_name) o número si no tiene
    const panelNombre = document.querySelector('#colInfo h6');
    if (panelNombre) {
        panelNombre.textContent = conv.custom_name || conv.wa_name || conv.phone_number || numero;
    }

    // small.text-muted → número real siempre
    const panelSub = document.querySelector('#colInfo small.text-muted');
    if (panelSub) {
       panelSub.textContent = formatearNumero(conv.phone_number);
    }
}

function abrirChat(numero) {
    mostrarChat();
    chatActivo.numero = numero;
    chatActivo.nombre = todasLasConversaciones[numero].nombre;

    const conv = todasLasConversaciones[numero];

    // Marcar como activo
    document.querySelectorAll('.chat-item').forEach(i => i.classList.remove('active-chat'));
    document.querySelector(`[data-numero="${numero}"]`)?.classList.add('active-chat');

    // Actualizar header
    const headerNumero = document.querySelector('#colChat h6');
    if (headerNumero) {
        headerNumero.textContent = chatActivo.nombre;
    }

    // Actualizar subtítulo con wa_name o número si no hay wa_name
    const headerSub = document.querySelector('#colChat .text-muted');
    if (headerSub) {
        headerSub.textContent = conv.wa_name || conv.phone_number || '';
    }

    actualizarPanelInfo(numero);
    actualizarBtnOportunidad(numero);

    // Responsive: En móvil, ocultar lista de conversaciones
    if (window.innerWidth <= 768) {
        document.getElementById('colConversaciones').style.display = 'none';
        document.getElementById('colChat').classList.remove('col');
        document.getElementById('colChat').classList.add('col-12');
    }

    // Mostrar mensajes
    mostrarMensajes(numero);
    closeChatSearch();
}



// Función para mostrar iconos de estado de mensaje
function obtenerIconoEstado(status) {
    if (!status) return '';

    const iconos = {
        'sent': '<span class="status-icon status-sent">✓</span>',
        'delivered': '<span class="status-icon status-delivered"><svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M2.305,11.235a1,1,0,0,1,1.414.024l3.206,3.319L14.3,7.289A1,1,0,0,1,15.7,8.711l-8.091,8a1,1,0,0,1-.7.289H6.9a1,1,0,0,1-.708-.3L2.281,12.649A1,1,0,0,1,2.305,11.235ZM20.3,7.289l-7.372,7.289-.263-.273a1,1,0,1,0-1.438,1.39l.966,1a1,1,0,0,0,.708.3h.011a1,1,0,0,0,.7-.289l8.091-8A1,1,0,0,0,20.3,7.289Z"></path></svg></span>',
        'read': '<span class="status-icon status-read"><svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M2.305,11.235a1,1,0,0,1,1.414.024l3.206,3.319L14.3,7.289A1,1,0,0,1,15.7,8.711l-8.091,8a1,1,0,0,1-.7.289H6.9a1,1,0,0,1-.708-.3L2.281,12.649A1,1,0,0,1,2.305,11.235ZM20.3,7.289l-7.372,7.289-.263-.273a1,1,0,1,0-1.438,1.39l.966,1a1,1,0,0,0,.708.3h.011a1,1,0,0,0,.7-.289l8.091-8A1,1,0,0,0,20.3,7.289Z"></path></svg></span>',
        'failed': '<span class="status-icon status-failed"><svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M12 21C10.22 21 8.47991 20.4722 6.99987 19.4832C5.51983 18.4943 4.36628 17.0887 3.68509 15.4442C3.0039 13.7996 2.82567 11.99 3.17294 10.2442C3.5202 8.49836 4.37737 6.89472 5.63604 5.63604C6.89472 4.37737 8.49836 3.5202 10.2442 3.17294C11.99 2.82567 13.7996 3.0039 15.4442 3.68509C17.0887 4.36628 18.4943 5.51983 19.4832 6.99987C20.4722 8.47991 21 10.22 21 12C21 14.387 20.0518 16.6761 18.364 18.364C16.6761 20.0518 14.387 21 12 21ZM12 4.5C10.5166 4.5 9.0666 4.93987 7.83323 5.76398C6.59986 6.58809 5.63856 7.75943 5.07091 9.12988C4.50325 10.5003 4.35473 12.0083 4.64411 13.4632C4.9335 14.918 5.64781 16.2544 6.6967 17.3033C7.7456 18.3522 9.08197 19.0665 10.5368 19.3559C11.9917 19.6453 13.4997 19.4968 14.8701 18.9291C16.2406 18.3614 17.4119 17.4001 18.236 16.1668C19.0601 14.9334 19.5 13.4834 19.5 12C19.5 10.0109 18.7098 8.10323 17.3033 6.6967C15.8968 5.29018 13.9891 4.5 12 4.5Z"></path><path d="M12 13C11.8019 12.9974 11.6126 12.9176 11.4725 12.7775C11.3324 12.6374 11.2526 12.4481 11.25 12.25V8.75C11.25 8.55109 11.329 8.36032 11.4697 8.21967C11.6103 8.07902 11.8011 8 12 8C12.1989 8 12.3897 8.07902 12.5303 8.21967C12.671 8.36032 12.75 8.55109 12.75 8.75V12.25C12.7474 12.4481 12.6676 12.6374 12.5275 12.7775C12.3874 12.9176 12.1981 12.9974 12 13Z"></path><path d="M12 16C11.8019 15.9974 11.6126 15.9176 11.4725 15.7775C11.3324 15.6374 11.2526 15.4481 11.25 15.25V14.75C11.25 14.5511 11.329 14.3603 11.4697 14.2197C11.6103 14.079 11.8011 14 12 14C12.1989 14 12.3897 14.079 12.5303 14.2197C12.671 14.3603 12.75 14.5511 12.75 14.75V15.25C12.7474 15.4481 12.6676 15.6374 12.5275 15.7775C12.3874 15.9176 12.1981 15.9974 12 16Z"></path></svg></span>'
    };

    return iconos[status] || '';
}

// ===============================================
// MOSTRAR MENSAJES EN EL CHAT (CON IMÁGENES)
// ===============================================
function mostrarMensajes(numero) {
    const chatMessages = document.querySelector('.chat-messages');
    if (!chatMessages) return;

    chatMessages.innerHTML = '';

    const conversacion = todasLasConversaciones[numero];
    if (!conversacion) return;

    conversacion.mensajes.forEach(msg => {
        const esEnviado = msg.tipo === 'enviado';

        // Detectar tipo de contenido
        const esMedia = msg.media_url && (msg.media_type === 'image' || msg.media_type === 'sticker');
        const esDocumento = msg.media_url && msg.media_type === 'document';
        const esAudio = msg.media_url && (msg.media_type === 'audio' || msg.media_type === 'voice');
        const esVideo = msg.media_url && msg.media_type === 'video';
        const esSticker = msg.media_type === 'sticker';
        const esUbicacion = msg.media_type === 'location' && msg.location;

        let contenido = '';
        let estilosContainer = '';

        if (esMedia) {
            estilosContainer = 'overflow: hidden; padding: 0;';

            contenido = `
                <img src="${msg.media_url}" 
                     alt="${esSticker ? 'Sticker' : 'Imagen'}" 
                     style="max-width: ${esSticker ? '200px' : '300px'};  
                            max-height: ${esSticker ? '200px' : '300px'}; 
                            width: 100%;
                            height: auto;
                            border-radius: ${esSticker ? '0px' : '8px'};
                            display: block; 
                            object-fit: ${esSticker ? 'contain' : 'cover'};
                            cursor: pointer;
                            ${esSticker ? 'background: transparent;' : ''}"
                     onclick="window.open('${msg.media_url}', '_blank')">
                ${msg.texto && !msg.texto.includes('[IMAGEN]') && !msg.texto.includes('[STICKER]') ?
                    `<p style="margin: 8px 10px 6px 10px; font-size: 0.9rem;">${msg.texto}</p>` : ''}
            `;
        } else if (esDocumento) {
            // 📄 DOCUMENTO - ✅ CORRECCIÓN: Usar msg.filename en lugar de msg.media?.filename
            const filename = msg.filename || msg.media_url?.split('/').pop() || 'documento';
            const extension = filename.split('.').pop().toUpperCase();

            // Configuración de iconos SVG según tipo de archivo
            const tiposArchivo = {
                'PDF': {
                    color: '#E74C3C',
                    bgColor: '#FADBD8',
                    svg: `<svg height="40px" width="40px" version="1.1" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><path style="fill:#E2E5E7;" d="M128,0c-17.6,0-32,14.4-32,32v448c0,17.6,14.4,32,32,32h320c17.6,0,32-14.4,32-32V128L352,0H128z"></path><path style="fill:#B0B7BD;" d="M384,128h96L352,0v96C352,113.6,366.4,128,384,128z"></path><polygon style="fill:#CAD1D8;" points="480,224 384,128 480,128"></polygon><path style="fill:#F15642;" d="M416,416c0,8.8-7.2,16-16,16H48c-8.8,0-16-7.2-16-16V256c0-8.8,7.2-16,16-16h352c8.8,0,16,7.2,16,16V416z"></path></svg>`
                },
                'DOC': {
                    color: '#2E86DE',
                    bgColor: '#D6EAF8',
                    svg: `<svg height="40px" width="40px" version="1.1" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><path style="fill:#E2E5E7;" d="M128,0c-17.6,0-32,14.4-32,32v448c0,17.6,14.4,32,32,32h320c17.6,0,32-14.4,32-32V128L352,0H128z"></path><path style="fill:#B0B7BD;" d="M384,128h96L352,0v96C352,113.6,366.4,128,384,128z"></path><polygon style="fill:#CAD1D8;" points="480,224 384,128 480,128"></polygon><path style="fill:#50BEE8;" d="M416,416c0,8.8-7.2,16-16,16H48c-8.8,0-16-7.2-16-16V256c0-8.8,7.2-16,16-16h352c8.8,0,16,7.2,16,16V416z"></path></svg>`
                },
                'DOCX': {
                    color: '#2E86DE',
                    bgColor: '#D6EAF8',
                    svg: `<svg height="40px" width="40px" version="1.1" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><path style="fill:#E2E5E7;" d="M128,0c-17.6,0-32,14.4-32,32v448c0,17.6,14.4,32,32,32h320c17.6,0,32-14.4,32-32V128L352,0H128z"></path><path style="fill:#B0B7BD;" d="M384,128h96L352,0v96C352,113.6,366.4,128,384,128z"></path><polygon style="fill:#CAD1D8;" points="480,224 384,128 480,128"></polygon><path style="fill:#50BEE8;" d="M416,416c0,8.8-7.2,16-16,16H48c-8.8,0-16-7.2-16-16V256c0-8.8,7.2-16,16-16h352c8.8,0,16,7.2,16,16V416z"></path></svg>`
                },
                'XLS': {
                    color: '#27AE60',
                    bgColor: '#D5F4E6',
                    svg: `<svg height="40px" width="40px" version="1.1" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><path style="fill:#E2E5E7;" d="M128,0c-17.6,0-32,14.4-32,32v448c0,17.6,14.4,32,32,32h320c17.6,0,32-14.4,32-32V128L352,0H128z"></path><path style="fill:#B0B7BD;" d="M384,128h96L352,0v96C352,113.6,366.4,128,384,128z"></path><polygon style="fill:#CAD1D8;" points="480,224 384,128 480,128"></polygon><path style="fill:#84BD5A;" d="M416,416c0,8.8-7.2,16-16,16H48c-8.8,0-16-7.2-16-16V256c0-8.8,7.2-16,16-16h352c8.8,0,16,7.2,16,16V416z"></path></svg>`
                },
                'XLSX': {
                    color: '#27AE60',
                    bgColor: '#D5F4E6',
                    svg: `<svg height="40px" width="40px" version="1.1" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><path style="fill:#E2E5E7;" d="M128,0c-17.6,0-32,14.4-32,32v448c0,17.6,14.4,32,32,32h320c17.6,0,32-14.4,32-32V128L352,0H128z"></path><path style="fill:#B0B7BD;" d="M384,128h96L352,0v96C352,113.6,366.4,128,384,128z"></path><polygon style="fill:#CAD1D8;" points="480,224 384,128 480,128"></polygon><path style="fill:#84BD5A;" d="M416,416c0,8.8-7.2,16-16,16H48c-8.8,0-16-7.2-16-16V256c0-8.8,7.2-16,16-16h352c8.8,0,16,7.2,16,16V416z"></path></svg>`
                },
                'PPT': {
                    color: '#E67E22',
                    bgColor: '#FAE5D3',
                    svg: `<svg height="40px" width="40px" version="1.1" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><path style="fill:#E2E5E7;" d="M128,0c-17.6,0-32,14.4-32,32v448c0,17.6,14.4,32,32,32h320c17.6,0,32-14.4,32-32V128L352,0H128z"></path><path style="fill:#B0B7BD;" d="M384,128h96L352,0v96C352,113.6,366.4,128,384,128z"></path><polygon style="fill:#CAD1D8;" points="480,224 384,128 480,128"></polygon><path style="fill:#F15642;" d="M416,416c0,8.8-7.2,16-16,16H48c-8.8,0-16-7.2-16-16V256c0-8.8,7.2-16,16-16h352c8.8,0,16,7.2,16,16V416z"></path></svg>`
                },
                'PPTX': {
                    color: '#E67E22',
                    bgColor: '#FAE5D3',
                    svg: `<svg height="40px" width="40px" version="1.1" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><path style="fill:#E2E5E7;" d="M128,0c-17.6,0-32,14.4-32,32v448c0,17.6,14.4,32,32,32h320c17.6,0,32-14.4,32-32V128L352,0H128z"></path><path style="fill:#B0B7BD;" d="M384,128h96L352,0v96C352,113.6,366.4,128,384,128z"></path><polygon style="fill:#CAD1D8;" points="480,224 384,128 480,128"></polygon><path style="fill:#F15642;" d="M416,416c0,8.8-7.2,16-16,16H48c-8.8,0-16-7.2-16-16V256c0-8.8,7.2-16,16-16h352c8.8,0,16,7.2,16,16V416z"></path></svg>`
                },
                'TXT': {
                    color: '#95A5A6',
                    bgColor: '#ECF0F1',
                    svg: `<svg height="40px" width="40px" version="1.1" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><path style="fill:#E2E5E7;" d="M128,0c-17.6,0-32,14.4-32,32v448c0,17.6,14.4,32,32,32h320c17.6,0,32-14.4,32-32V128L352,0H128z"></path><path style="fill:#B0B7BD;" d="M384,128h96L352,0v96C352,113.6,366.4,128,384,128z"></path><polygon style="fill:#CAD1D8;" points="480,224 384,128 480,128"></polygon><path style="fill:#576D7E;" d="M416,416c0,8.8-7.2,16-16,16H48c-8.8,0-16-7.2-16-16V256c0-8.8,7.2-16,16-16h352c8.8,0,16,7.2,16,16V416z"></path></svg>`
                },
                'ZIP': {
                    color: '#8E44AD',
                    bgColor: '#EBDEF0',
                    svg: `<svg height="40px" width="40px" version="1.1" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><path style="fill:#E2E5E7;" d="M128,0c-17.6,0-32,14.4-32,32v448c0,17.6,14.4,32,32,32h320c17.6,0,32-14.4,32-32V128L352,0H128z"></path><path style="fill:#B0B7BD;" d="M384,128h96L352,0v96C352,113.6,366.4,128,384,128z"></path><polygon style="fill:#CAD1D8;" points="480,224 384,128 480,128"></polygon><path style="fill:#84BD5A;" d="M416,416c0,8.8-7.2,16-16,16H48c-8.8,0-16-7.2-16-16V256c0-8.8,7.2-16,16-16h352c8.8,0,16,7.2,16,16V416z"></path></svg>`
                },
                'RAR': {
                    color: '#8E44AD',
                    bgColor: '#EBDEF0',
                    svg: `<svg height="40px" width="40px" version="1.1" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><path style="fill:#E2E5E7;" d="M128,0c-17.6,0-32,14.4-32,32v448c0,17.6,14.4,32,32,32h320c17.6,0,32-14.4,32-32V128L352,0H128z"></path><path style="fill:#B0B7BD;" d="M384,128h96L352,0v96C352,113.6,366.4,128,384,128z"></path><polygon style="fill:#CAD1D8;" points="480,224 384,128 480,128"></polygon><path style="fill:#50BEE8;" d="M416,416c0,8.8-7.2,16-16,16H48c-8.8,0-16-7.2-16-16V256c0-8.8,7.2-16,16-16h352c8.8,0,16,7.2,16,16V416z"></path></svg>`
                },
                'CSV': {
                    color: '#16A085',
                    bgColor: '#D1F2EB',
                    svg: `<svg height="40px" width="40px" viewBox="-4 0 64 64" xmlns="http://www.w3.org/2000/svg" fill="#45B058"><path d="M5.106 0c-2.802 0-5.073 2.272-5.073 5.074v53.841c0 2.803 2.271 5.074 5.073 5.074h45.774c2.801 0 5.074-2.271 5.074-5.074v-38.605l-18.903-20.31h-31.945z" fill="#45B058"></path></svg>`
                }
            };

            const archivoInfo = tiposArchivo[extension] || {
                color: '#7F8C8D',
                bgColor: '#F8F9FA',
                svg: `<svg width="40" height="40" viewBox="0 0 24 24" fill="none"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" fill="#7F8C8D" opacity="0.2"/><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6z" stroke="#7F8C8D" stroke-width="2"/><path d="M14 2v6h6" stroke="#7F8C8D" stroke-width="2"/></svg>`
            };

            estilosContainer = 'padding: 0; overflow: hidden;';

            contenido = `
                <a href="${msg.media_url}" 
                   download="${filename}"
                   class="documento-descarga"
                   style="text-decoration: none; color: inherit; display: flex; align-items: center; gap: 14px; padding: 12px 16px; background: linear-gradient(135deg, ${archivoInfo.bgColor} 0%, #ffffff 100%); transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);"
                   onmouseover="this.style.transform='translateX(4px)'; this.style.boxShadow='0 4px 12px rgba(0,0,0,0.08)'; this.querySelector('.download-icon').style.transform='translateY(2px)';"
                   onmouseout="this.style.transform='translateX(0)'; this.style.boxShadow='none'; this.querySelector('.download-icon').style.transform='translateY(0)';">
                    
                    <div style="display: flex; align-items: center; justify-content: center; width: 48px; height: 48px; background: ${archivoInfo.color}15; border-radius: 12px; flex-shrink: 0; box-shadow: 0 2px 8px ${archivoInfo.color}20;">
                        ${archivoInfo.svg}
                    </div>
                    
                    <div style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px;">
                        <div style="font-weight: 600; font-size: 0.95rem; color: #2C3E50; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                            ${filename}
                        </div>
                        <div style="display: flex; align-items: center; gap: 8px; font-size: 0.8rem; color: #7F8C8D; font-weight: 500;">
                            <span style="background: ${archivoInfo.color}; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.7rem; font-weight: 600; letter-spacing: 0.5px;">${extension}</span>
                            <span style="opacity: 0.8;">• Click para descargar</span>
                        </div>
                    </div>
                    
                    <div class="download-icon" style="display: flex; align-items: center; justify-content: center; width: 36px; height: 36px; background: ${archivoInfo.color}10; border-radius: 50%; flex-shrink: 0; transition: all 0.3s ease;">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="${archivoInfo.color}" stroke-width="2.5">
                            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                            <polyline points="7 10 12 15 17 10"></polyline>
                            <line x1="12" y1="15" x2="12" y2="3"></line>
                        </svg>
                    </div>
                </a>
            `;
        } else if (esAudio) {
            const audioId = `audio-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
            estilosContainer = 'padding: 8px 12px; min-width: 260px;';

            const numBarras = 30;
            const barras = Array.from({ length: numBarras }, (_, i) => {
                const height = Math.floor(Math.random() * 16) + 8;
                return `<div class="wave-bar-${audioId}" data-index="${i}" style="flex: 1; background: #D1D7DB; border-radius: 2px; height: ${height}px; transition: background 0.15s ease;"></div>`;
            }).join('');

            contenido = `
                <div style="display: flex; align-items: center; gap: 8px;">
                    <button id="playBtn-${audioId}" style="width: 42px; height: 42px; border-radius: 50%; background: var(--bs-primary); border: none; display: flex; align-items: center; justify-content: center; cursor: pointer; flex-shrink: 0; padding: 0;">
                        <svg id="playIcon-${audioId}" width="22" height="22" viewBox="0 0 24 24" fill="white"><path d="M8 5v14l11-7z"/></svg>
                        <svg id="pauseIcon-${audioId}" width="18" height="18" viewBox="0 0 24 24" fill="white" style="display: none;"><path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z"/></svg>
                    </button>
                    <div id="waveContainer-${audioId}" style="flex: 1; min-width: 150px; display: flex; align-items: center; gap: 2px; height: 32px; cursor: pointer;">${barras}</div>
                    <div style="color: #667781; font-size: 0.75rem; min-width: 35px; text-align: right;"><span id="time-${audioId}">0:00</span></div>
                </div>
                <audio id="${audioId}" preload="metadata" style="display: none;">
                    <source src="${msg.media_url}" type="audio/mpeg">
                    <source src="${msg.media_url}" type="audio/ogg; codecs=opus">
                    <source src="${msg.media_url}" type="audio/ogg">
                </audio>
            `;

            setTimeout(() => {
                const audio = document.getElementById(audioId);
                const playBtn = document.getElementById(`playBtn-${audioId}`);
                const playIcon = document.getElementById(`playIcon-${audioId}`);
                const pauseIcon = document.getElementById(`pauseIcon-${audioId}`);
                const time = document.getElementById(`time-${audioId}`);
                const waveContainer = document.getElementById(`waveContainer-${audioId}`);
                const waveBars = document.querySelectorAll(`.wave-bar-${audioId}`);

                if (!audio || !playBtn || !waveContainer) return;

                function updateWaveBars(percentage) {
                    const totalBarras = waveBars.length;
                    const barrasColoreadas = Math.floor((percentage / 100) * totalBarras);
                    waveBars.forEach((bar, index) => {
                        bar.style.background = index < barrasColoreadas ? 'rgba(var(--bs-primary-rgb), 0.5)' : '#D1D7DB';
                    });
                }

                playBtn.addEventListener('click', function () {
                    if (audio.paused) {
                        audio.play();
                        playIcon.style.display = 'none';
                        pauseIcon.style.display = 'block';
                    } else {
                        audio.pause();
                        playIcon.style.display = 'block';
                        pauseIcon.style.display = 'none';
                    }
                });

                audio.addEventListener('timeupdate', function () {
                    const percentage = (audio.currentTime / audio.duration) * 100;
                    updateWaveBars(percentage);
                    const remaining = audio.duration - audio.currentTime;
                    const minutes = Math.floor(remaining / 60);
                    const seconds = Math.floor(remaining % 60);
                    time.textContent = minutes + ':' + (seconds < 10 ? '0' : '') + seconds;
                });

                audio.addEventListener('loadedmetadata', function () {
                    if (audio.duration && !isNaN(audio.duration)) {
                        const minutes = Math.floor(audio.duration / 60);
                        const seconds = Math.floor(audio.duration % 60);
                        time.textContent = minutes + ':' + (seconds < 10 ? '0' : '') + seconds;
                    }
                });

                waveContainer.addEventListener('click', function (e) {
                    if (!audio.duration || isNaN(audio.duration)) return;
                    const rect = waveContainer.getBoundingClientRect();
                    const clickX = e.clientX - rect.left;
                    const percentage = (clickX / rect.width) * 100;
                    audio.currentTime = (percentage / 100) * audio.duration;
                    updateWaveBars(percentage);
                });

                audio.addEventListener('ended', function () {
                    playIcon.style.display = 'block';
                    pauseIcon.style.display = 'none';
                    updateWaveBars(0);
                });
            }, 100);
        } else if (esVideo) {
            estilosContainer = 'overflow: hidden; padding: 0;';
            contenido = `
                <video controls style="max-width: 400px; max-height: 400px; width: 100%; height: auto; border-radius: 8px; display: block; background: #000;" preload="metadata">
                    <source src="${msg.media_url}" type="${msg.media?.mime_type || 'video/mp4'}">
                    Tu navegador no soporta video.
                </video>
                ${msg.texto && !msg.texto.includes('[VIDEO]') && msg.texto !== '[🎥 VIDEO]' ?
                    `<p style="margin: 8px 10px 6px 10px; font-size: 0.9rem;">${msg.texto}</p>` : ''}
            `;
        } else if (esUbicacion) {
            // 📍 UBICACIÓN
            const lat = msg.location.latitude;
            const lon = msg.location.longitude;
            const nombre = msg.location.name || '';
            const direccion = msg.location.address || '';
            const mapsUrl = `https://www.google.com/maps?q=${lat},${lon}`;

            estilosContainer = 'padding: 0; overflow: hidden;';

            contenido = `
                <a href="${mapsUrl}" 
                target="_blank"
                style="text-decoration: none; color: inherit; display: block;">
                    
                    <!-- Mapa con OpenStreetMap -->
                    <div style="width: 100%; height: 200px; position: relative; background: #e5e5e5; border-radius: 8px 8px 0 0; overflow: hidden;">
                        <iframe
                            width="100%"
                            height="200"
                            frameborder="0"
                            scrolling="no"
                            marginheight="0"
                            marginwidth="0"
                            src="https://www.openstreetmap.org/export/embed.html?bbox=${lon - 0.01},${lat - 0.01},${lon + 0.01},${lat + 0.01}&layer=mapnik&marker=${lat},${lon}"
                            style="border: none; display: block;">
                        </iframe>
                        
                        <!-- Pin personalizado -->
                        <div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -100%); z-index: 10; pointer-events: none;">
                            <svg width="40" height="50" viewBox="0 0 24 30" fill="none">
                                <path d="M12 0C7.31 0 3.5 3.81 3.5 8.5c0 6.56 8.5 20.5 8.5 20.5s8.5-13.94 8.5-20.5C20.5 3.81 16.69 0 12 0zm0 11.5c-1.66 0-3-1.34-3-3s1.34-3 3-3 3 1.34 3 3-1.34 3-3 3z" fill="#dc3545"/>
                                <circle cx="12" cy="8.5" r="2" fill="white"/>
                            </svg>
                        </div>
                    </div>
                    
                    <!-- Información -->
                    <div style="padding: 12px 16px; background: linear-gradient(135deg, #FFF5F5 0%, #ffffff 100%);">
                        ${nombre ? `
                            <div style="font-weight: 600; font-size: 0.95rem; color: #2C3E50; margin-bottom: 4px;">
                                📍 ${nombre}
                            </div>
                        ` : ''}
                        
                        ${direccion ? `
                            <div style="font-size: 0.85rem; color: #7F8C8D; margin-bottom: 8px;">
                                ${direccion}
                            </div>
                        ` : ''}
                        
                        <div style="display: flex; align-items: center; gap: 8px; font-size: 0.8rem; color: #DC3545; font-weight: 500;">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z"/>
                                <circle cx="12" cy="9" r="2.5"/>
                            </svg>
                            <span>${lat.toFixed(6)}, ${lon.toFixed(6)}</span>
                        </div>
                        
                        <div style="margin-top: 8px; font-size: 0.75rem; color: #95A5A6;">
                            🔗 Click para abrir en Google Maps
                        </div>
                    </div>
                </a>
            `;
        } else {
            estilosContainer = 'padding: 0.5rem;';
            contenido = `<p class="mb-0">${msg.texto}</p>`;
        }

        let bubbleClass = esEnviado 
            ? 'bg-primary text-white' 
            : 'bg-white border text-dark';
            
        let bubbleRadius = esEnviado 
            ? '12px 12px 0 12px' 
            : '12px 12px 12px 0';
            
        if (esAudio || esMedia || esVideo) {
            bubbleClass = esEnviado ? 'bg-light' : 'bg-white border';
            if (esEnviado) {
                // Keep text dark if light background
            }
        }

        const mensajeHTML = `
            <div class="d-flex flex-column ${esEnviado ? 'align-items-end' : 'align-items-start'} mb-3 w-100">
                <div class="p-2 ${bubbleClass} shadow-sm"
                     style="min-width: ${esMedia || esDocumento || esAudio || esVideo ? 'auto' : '10%'}; 
                            max-width: ${esMedia ? (esSticker ? '220px' : '320px') : (esDocumento ? '400px' : (esAudio ? '350px' : (esVideo ? '420px' : '75%')))}; 
                            border-radius: ${bubbleRadius};
                            ${estilosContainer}
                            display: inline-block;">
                    ${contenido}
                </div>
                <div class="d-flex align-items-center mt-1 ${esEnviado ? 'pe-1' : 'ps-1'}">
                    <small class="text-muted" style="font-size: 0.72rem;">
                        ${msg.hora}
                    </small>
                    ${esEnviado ? obtenerIconoEstado(msg.status) : ''}
                </div>
            </div>
        `;

        chatMessages.insertAdjacentHTML('beforeend', mensajeHTML);
    });

    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function manejarEnvio() {
    const barraGrabacion = document.getElementById('barraGrabacion');
    const estaGrabando = barraGrabacion.style.display !== 'none';

    if (estaGrabando) {
        detenerYEnviarGrabacion(); // envía el audio
    } else {
        enviarMensajeWhatsApp();   // envía el texto
    }
}
// ===============================================
// ENVIAR IMÁGENES, VIDEOS Y DOCUMENTOS
// ===============================================
document.addEventListener('DOMContentLoaded', function () {
    // 📸 Input de imágenes/videos
    const inputImagen = document.getElementById('inputImagenWhatsApp');

    if (inputImagen) {
        inputImagen.addEventListener('change', function (e) {
            const file = e.target.files[0];

            if (!file) return;

            const esVideo = file.type.startsWith('video/');
            const esImagen = file.type.startsWith('image/');

            const maxSize = esVideo ? 16 * 1024 * 1024 : 5 * 1024 * 1024;
            const maxSizeText = esVideo ? '16MB' : '5MB';
            const tipoTexto = esVideo ? 'video' : 'imagen';

            if (file.size > maxSize) {
                Swal.fire({
                    icon: 'error',
                    title: `${tipoTexto.charAt(0).toUpperCase() + tipoTexto.slice(1)} muy grande`,
                    text: `El ${tipoTexto} no puede superar ${maxSizeText}`,
                    confirmButtonColor: '#d33'
                });
                inputImagen.value = '';
                return;
            }

            const allowedTypes = [
                'image/jpeg', 'image/jpg', 'image/png', 'image/webp',
                'video/mp4', 'video/3gpp'
            ];

            if (!allowedTypes.includes(file.type)) {
                Swal.fire({
                    icon: 'error',
                    title: 'Formato no válido',
                    text: 'Solo se permiten imágenes (JPG, PNG, WEBP) y videos (MP4, 3GPP)',
                    confirmButtonColor: '#d33'
                });
                inputImagen.value = '';
                return;
            }

            if (!chatActivo.numero) {
                Swal.fire({
                    icon: 'warning',
                    title: 'No hay chat seleccionado',
                    text: 'Selecciona un chat primero',
                    timer: 2000
                });
                inputImagen.value = '';
                return;
            }

            if (esImagen) {
                mostrarPreviewImagen(file);
            } else if (esVideo) {
                mostrarPreviewVideo(file);
            }
        });
    }

    // 📄 Input de documentos
    const inputDocumento = document.getElementById('inputDocumentoWhatsApp');

    if (inputDocumento) {
        console.log('✅ Event listener de documentos registrado');

        inputDocumento.addEventListener('change', function (e) {
            console.log('📁 Archivo seleccionado');
            const file = e.target.files[0];

            if (!file) {
                console.log('⚠️ No hay archivo');
                return;
            }

            console.log('📄 Archivo:', file.name, 'Tipo:', file.type, 'Tamaño:', file.size);

            const allowedTypes = [
                'application/pdf',
                'application/msword',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'application/vnd.ms-excel',
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'application/vnd.ms-powerpoint',
                'application/vnd.openxmlformats-officedocument.presentationml.presentation',
                'text/plain',
                'application/zip',
                'application/x-zip-compressed'
            ];

            const extension = file.name.split('.').pop().toLowerCase();
            const allowedExtensions = ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'zip'];

            if (!allowedTypes.includes(file.type) && !allowedExtensions.includes(extension)) {
                Swal.fire({
                    icon: 'error',
                    title: 'Formato no válido',
                    text: 'Solo PDF, Word, Excel, PowerPoint, TXT o ZIP',
                    confirmButtonColor: '#d33'
                });
                inputDocumento.value = '';
                return;
            }

            if (file.size > 100 * 1024 * 1024) {
                Swal.fire({
                    icon: 'error',
                    title: 'Archivo muy grande',
                    text: 'El documento no puede superar 100MB',
                    confirmButtonColor: '#d33'
                });
                inputDocumento.value = '';
                return;
            }

            if (!chatActivo.numero) {
                Swal.fire({
                    icon: 'warning',
                    title: 'No hay chat seleccionado',
                    text: 'Selecciona un chat primero',
                    timer: 2000
                });
                inputDocumento.value = '';
                return;
            }

            console.log('✅ Validaciones pasadas, mostrando preview');
            mostrarPreviewDocumento(file);
        });
    } else {
        console.error('❌ No se encontró el input inputDocumentoWhatsApp');
    }
});

// ============================================
// MODAL DE FOTOS Y VIDEOS (ESTILO UPLOAD)
// ============================================
let archivosSeleccionados = [];

function abrirModalFotosVideos() {
    archivosSeleccionados = [];
    renderModalFotos();
}

function renderModalFotos() {
    // Generar thumbnails
    let thumbsHTML = '';
    for (let i = 0; i < 6; i++) {
        if (i < archivosSeleccionados.length) {
            const archivo = archivosSeleccionados[i];
            const esVideo = archivo.esVideo || false;
            thumbsHTML += `
                <div style="position:relative; width:80px; height:80px; border-radius:8px; overflow:hidden; border:1px solid #e0e0e0; flex-shrink:0;">
                    ${esVideo
                        ? `<img src="${archivo.preview}" style="width:100%;height:100%;object-fit:cover;">
                           <div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);background:rgba(0,0,0,0.5);border-radius:50%;width:24px;height:24px;display:flex;align-items:center;justify-content:center;">
                               <svg width="12" height="12" viewBox="0 0 24 24" fill="white"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
                           </div>`
                        : `<img src="${archivo.preview}" style="width:100%;height:100%;object-fit:cover;">`
                    }
                    <button onclick="eliminarArchivoSeleccionado(${i})" style="position:absolute;top:2px;right:2px;background:#ff4444;color:white;border:none;border-radius:50%;width:18px;height:18px;font-size:11px;cursor:pointer;display:flex;align-items:center;justify-content:center;line-height:1;padding:0;">✕</button>
                </div>`;
        } else {
            thumbsHTML += `
                <div style="width:80px;height:80px;border-radius:8px;border:1px solid #e8e8e8;background:#f8f8f8;flex-shrink:0;"></div>`;
        }
    }

    const totalSize = archivosSeleccionados.reduce((sum, a) => sum + a.file.size, 0);
    const totalSizeMB = (totalSize / 1024 / 1024).toFixed(2);
    const hayArchivos = archivosSeleccionados.length > 0;

    Swal.fire({
        title: '',
        html: `
            <div style="text-align:left;margin-bottom:10px;">
                <h6 style="font-weight:600;color:#1a1a1a;margin:0;font-size:1rem;">Fotos y Videos</h6>
            </div>

            <div id="dropZoneFotos" 
                 style="border:2px dashed #d0d0d0;border-radius:12px;padding:24px 20px;text-align:center;background:#fafafa;cursor:pointer;transition:all 0.2s ease;"
                 onclick="document.getElementById('inputFotosModal').click();"
                 ondragover="event.preventDefault();this.style.borderColor='#25d366';this.style.background='#f0faf4';"
                 ondragleave="this.style.borderColor='#d0d0d0';this.style.background='#fafafa';"
                 ondrop="event.preventDefault();this.style.borderColor='#d0d0d0';this.style.background='#fafafa';agregarArchivosDesdeInput(event.dataTransfer.files);">
                <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#999" stroke-width="1.5">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                    <polyline points="17 8 12 3 7 8"></polyline>
                    <line x1="12" y1="3" x2="12" y2="15"></line>
                </svg>
                <p style="margin:8px 0 2px;font-weight:600;color:#333;font-size:0.9rem;">Upload</p>
                <p style="margin:0;color:#999;font-size:0.78rem;">Choose images or drag & drop it here.</p>
                <p style="margin:4px 0 0;color:#bbb;font-size:0.72rem;">JPG, JPEG, PNG, WEBP, MP4. Max 20 MB.</p>
            </div>

            <input type="file" id="inputFotosModal" accept="image/jpeg,image/png,image/webp,video/mp4,video/3gpp" multiple style="display:none;" onchange="agregarArchivosDesdeInput(this.files);">

            <div style="display:flex;gap:8px;margin-top:14px;overflow-x:auto;padding-bottom:4px;">
                ${thumbsHTML}
            </div>

            ${hayArchivos ? `<p style="text-align:left;margin:8px 0 0;color:#888;font-size:0.78rem;">${archivosSeleccionados.length} archivo${archivosSeleccionados.length > 1 ? 's' : ''} · ${totalSizeMB} MB</p>` : ''}

            <div style="margin-top:12px;">
                <input type="text" id="imagenCaptionModal" class="form-control" placeholder="Agregar texto (opcional)" value="${document.getElementById('imagenCaptionModal')?.value || ''}" style="border:1.5px solid #e0e0e0;border-radius:10px;padding:10px 14px;font-size:0.9rem;">
            </div>
        `,
        showCancelButton: true,
        confirmButtonText: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right:6px;"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg> Enviar${hayArchivos ? ' (' + archivosSeleccionados.length + ')' : ''}`,
        cancelButtonText: 'Cancelar',
        confirmButtonColor: hayArchivos ? '#25d366' : '#ccc',
        cancelButtonColor: '#6c757d',
        width: 440,
        padding: '20px',
        customClass: {
            popup: 'preview-imagen-popup',
            confirmButton: 'preview-btn-enviar',
            cancelButton: 'preview-btn-cancelar'
        },
        didOpen: () => {
            const caption = document.getElementById('imagenCaptionModal');
            if (caption) {
                caption.addEventListener('focus', function () {
                    this.style.borderColor = '#25d366';
                    this.style.boxShadow = '0 0 0 3px rgba(37, 211, 102, 0.15)';
                });
                caption.addEventListener('blur', function () {
                    this.style.borderColor = '#e0e0e0';
                    this.style.boxShadow = 'none';
                });
            }
        },
        preConfirm: () => {
            if (archivosSeleccionados.length === 0) {
                Swal.showValidationMessage('Selecciona al menos un archivo');
                return false;
            }
            return document.getElementById('imagenCaptionModal')?.value || '';
        }
    }).then((result) => {
        if (result.isConfirmed) {
            enviarMultiplesArchivos(archivosSeleccionados, result.value);
        }
        // Limpiar previews blob restantes
        archivosSeleccionados.forEach(a => {
            if (a.preview.startsWith('blob:')) URL.revokeObjectURL(a.preview);
        });
    });
}

function agregarArchivosDesdeInput(files) {
    const allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp', 'video/mp4', 'video/3gpp'];
    const maxSize = 20 * 1024 * 1024;

    let pendientes = 0;

    for (let i = 0; i < files.length; i++) {
        if (archivosSeleccionados.length + pendientes >= 6) break;

        const file = files[i];
        if (!allowedTypes.includes(file.type)) continue;
        if (file.size > maxSize) continue;

        const yaExiste = archivosSeleccionados.some(a => a.file.name === file.name && a.file.size === file.size);
        if (yaExiste) continue;

        pendientes++;
        const esVideo = file.type.startsWith('video/');

        if (esVideo) {
            // Para videos: usar placeholder con ícono de play
            const sizeMB = (file.size / 1024 / 1024).toFixed(1);
            // Crear un canvas con fondo gris e ícono de play como thumbnail
            const canvas = document.createElement('canvas');
            canvas.width = 160;
            canvas.height = 160;
            const ctx = canvas.getContext('2d');
            // Fondo gris
            ctx.fillStyle = '#2a2a2a';
            ctx.fillRect(0, 0, 160, 160);
            // Ícono play
            ctx.fillStyle = 'rgba(255,255,255,0.8)';
            ctx.beginPath();
            ctx.moveTo(60, 45);
            ctx.lineTo(110, 80);
            ctx.lineTo(60, 115);
            ctx.closePath();
            ctx.fill();
            // Texto con tamaño
            ctx.fillStyle = 'rgba(255,255,255,0.6)';
            ctx.font = '12px Arial';
            ctx.textAlign = 'center';
            ctx.fillText(sizeMB + ' MB', 80, 145);

            const thumbnail = canvas.toDataURL('image/jpeg', 0.8);
            archivosSeleccionados.push({ file, preview: thumbnail, esVideo: true });
            pendientes--;
            if (pendientes === 0) renderModalFotos();
        } else {
            // Para imágenes usar base64 (persiste al re-render del Swal)
            const reader = new FileReader();
            reader.onload = function (e) {
                archivosSeleccionados.push({ file, preview: e.target.result });
                pendientes--;
                if (pendientes === 0) renderModalFotos();
            };
            reader.readAsDataURL(file);
        }
    }

    // Si no hubo archivos válidos
    if (pendientes === 0 && files.length > 0) renderModalFotos();
}

function eliminarArchivoSeleccionado(index) {
    const archivo = archivosSeleccionados[index];
    if (archivo.preview.startsWith('blob:')) {
        URL.revokeObjectURL(archivo.preview);
    }
    archivosSeleccionados.splice(index, 1);
    renderModalFotos();
}

// ============================================
// ENVIAR MÚLTIPLES ARCHIVOS UNO POR UNO
// ============================================
async function enviarMultiplesArchivos(archivos, caption) {
    const total = archivos.length;

    for (let i = 0; i < archivos.length; i++) {
        const archivo = archivos[i];
        // Solo el primer archivo lleva caption
        const captionActual = (i === 0) ? caption : '';

        try {
            await enviarUnArchivo(archivo.file, captionActual);
        } catch (e) {
            console.error('Error enviando archivo:', e);
        }
    }

    // Limpiar y recargar mensajes
    document.getElementById('inputImagenWhatsApp').value = '';
    if (chatActivo.numero) {
        mostrarMensajes(chatActivo.numero);
    }
}

function enviarUnArchivo(file, caption) {
    return new Promise((resolve, reject) => {
        const formData = new FormData();
        formData.append('imagen', file);
        formData.append('to', chatActivo.numero);
        formData.append('caption', caption);

        fetch('enviar_imagen_whatsapp.php', {
            method: 'POST',
            body: formData
        })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    agregarImagenEnviadaUI(data.file_url, caption);
                    resolve(data);
                } else {
                    reject(data.error?.message || 'Error al enviar');
                }
            })
            .catch(reject);
    });
}

function agregarDocumentoEnviadoUI(documentUrl, originalName) {
    const chatMessages = document.querySelector('.chat-messages');
    if (!chatMessages) return;

    const ahora = new Date();
    const hora = ahora.getHours().toString().padStart(2, '0') + ':' +
        ahora.getMinutes().toString().padStart(2, '0');

    // Obtener extensión
    const extension = originalName.split('.').pop().toUpperCase();

    // Configuración de iconos SVG según tipo de archivo (igual que en mostrarMensajes)
    const tiposArchivo = {
        'PDF': {
            color: '#E74C3C',
            bgColor: '#FADBD8',
            svg: `<svg height="40px" width="40px" version="1.1" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><path style="fill:#E2E5E7;" d="M128,0c-17.6,0-32,14.4-32,32v448c0,17.6,14.4,32,32,32h320c17.6,0,32-14.4,32-32V128L352,0H128z"></path><path style="fill:#B0B7BD;" d="M384,128h96L352,0v96C352,113.6,366.4,128,384,128z"></path><polygon style="fill:#CAD1D8;" points="480,224 384,128 480,128"></polygon><path style="fill:#F15642;" d="M416,416c0,8.8-7.2,16-16,16H48c-8.8,0-16-7.2-16-16V256c0-8.8,7.2-16,16-16h352c8.8,0,16,7.2,16,16V416z"></path><g><path style="fill:#FFFFFF;" d="M101.744,303.152c0-4.224,3.328-8.832,8.688-8.832h29.552c16.64,0,31.616,11.136,31.616,32.48c0,20.224-14.976,31.488-31.616,31.488h-21.36v16.896c0,5.632-3.584,8.816-8.192,8.816c-4.224,0-8.688-3.184-8.688-8.816V303.152z M118.624,310.432v31.872h21.36c8.576,0,15.36-7.568,15.36-15.504c0-8.944-6.784-16.368-15.36-16.368H118.624z"></path><path style="fill:#FFFFFF;" d="M196.656,384c-4.224,0-8.832-2.304-8.832-7.92v-72.672c0-4.592,4.608-7.936,8.832-7.936h29.296c58.464,0,57.184,88.528,1.152,88.528H196.656z M204.72,311.088V368.4h21.232c34.544,0,36.08-57.312,0-57.312H204.72z"></path><path style="fill:#FFFFFF;" d="M303.872,312.112v20.336h32.624c4.608,0,9.216,4.608,9.216,9.072c0,4.224-4.608,7.68-9.216,7.68h-32.624v26.864c0,4.48-3.184,7.92-7.664,7.92c-5.632,0-9.072-3.44-9.072-7.92v-72.672c0-4.592,3.456-7.936,9.072-7.936h44.912c5.632,0,8.96,3.344,8.96,7.936c0,4.096-3.328,8.704-8.96,8.704h-37.248V312.112z"></path></g></svg>`
        },
        'DOC': {
            color: '#2E86DE',
            bgColor: '#D6EAF8',
            svg: `<svg height="40px" width="40px" version="1.1" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><path style="fill:#E2E5E7;" d="M128,0c-17.6,0-32,14.4-32,32v448c0,17.6,14.4,32,32,32h320c17.6,0,32-14.4,32-32V128L352,0H128z"></path><path style="fill:#B0B7BD;" d="M384,128h96L352,0v96C352,113.6,366.4,128,384,128z"></path><polygon style="fill:#CAD1D8;" points="480,224 384,128 480,128"></polygon><path style="fill:#50BEE8;" d="M416,416c0,8.8-7.2,16-16,16H48c-8.8,0-16-7.2-16-16V256c0-8.8,7.2-16,16-16h352c8.8,0,16,7.2,16,16V416z"></path><g><path style="fill:#FFFFFF;" d="M92.576,384c-4.224,0-8.832-2.32-8.832-7.936v-72.656c0-4.608,4.608-7.936,8.832-7.936h29.296c58.464,0,57.168,88.528,1.136,88.528H92.576z M100.64,311.072v57.312h21.232c34.544,0,36.064-57.312,0-57.312H100.64z"></path></g></svg>`
        },
        'DOCX': {
            color: '#2E86DE',
            bgColor: '#D6EAF8',
            svg: `<svg height="40px" width="40px" version="1.1" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><path style="fill:#E2E5E7;" d="M128,0c-17.6,0-32,14.4-32,32v448c0,17.6,14.4,32,32,32h320c17.6,0,32-14.4,32-32V128L352,0H128z"></path><path style="fill:#B0B7BD;" d="M384,128h96L352,0v96C352,113.6,366.4,128,384,128z"></path><polygon style="fill:#CAD1D8;" points="480,224 384,128 480,128"></polygon><path style="fill:#50BEE8;" d="M416,416c0,8.8-7.2,16-16,16H48c-8.8,0-16-7.2-16-16V256c0-8.8,7.2-16,16-16h352c8.8,0,16,7.2,16,16V416z"></path><g><path style="fill:#FFFFFF;" d="M92.576,384c-4.224,0-8.832-2.32-8.832-7.936v-72.656c0-4.608,4.608-7.936,8.832-7.936h29.296c58.464,0,57.168,88.528,1.136,88.528H92.576z M100.64,311.072v57.312h21.232c34.544,0,36.064-57.312,0-57.312H100.64z"></path></g></svg>`
        },
        'XLS': {
            color: '#27AE60',
            bgColor: '#D5F4E6',
            svg: `<svg height="40px" width="40px" version="1.1" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><path style="fill:#E2E5E7;" d="M128,0c-17.6,0-32,14.4-32,32v448c0,17.6,14.4,32,32,32h320c17.6,0,32-14.4,32-32V128L352,0H128z"></path><path style="fill:#B0B7BD;" d="M384,128h96L352,0v96C352,113.6,366.4,128,384,128z"></path><polygon style="fill:#CAD1D8;" points="480,224 384,128 480,128"></polygon><path style="fill:#84BD5A;" d="M416,416c0,8.8-7.2,16-16,16H48c-8.8,0-16-7.2-16-16V256c0-8.8,7.2-16,16-16h352c8.8,0,16,7.2,16,16V416z"></path></svg>`
        },
        'XLSX': {
            color: '#27AE60',
            bgColor: '#D5F4E6',
            svg: `<svg height="40px" width="40px" version="1.1" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><path style="fill:#E2E5E7;" d="M128,0c-17.6,0-32,14.4-32,32v448c0,17.6,14.4,32,32,32h320c17.6,0,32-14.4,32-32V128L352,0H128z"></path><path style="fill:#B0B7BD;" d="M384,128h96L352,0v96C352,113.6,366.4,128,384,128z"></path><polygon style="fill:#CAD1D8;" points="480,224 384,128 480,128"></polygon><path style="fill:#84BD5A;" d="M416,416c0,8.8-7.2,16-16,16H48c-8.8,0-16-7.2-16-16V256c0-8.8,7.2-16,16-16h352c8.8,0,16,7.2,16,16V416z"></path></svg>`
        },
        'PPT': {
            color: '#E67E22',
            bgColor: '#FAE5D3',
            svg: `<svg height="40px" width="40px" version="1.1" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><path style="fill:#E2E5E7;" d="M128,0c-17.6,0-32,14.4-32,32v448c0,17.6,14.4,32,32,32h320c17.6,0,32-14.4,32-32V128L352,0H128z"></path><path style="fill:#B0B7BD;" d="M384,128h96L352,0v96C352,113.6,366.4,128,384,128z"></path><polygon style="fill:#CAD1D8;" points="480,224 384,128 480,128"></polygon><path style="fill:#F15642;" d="M416,416c0,8.8-7.2,16-16,16H48c-8.8,0-16-7.2-16-16V256c0-8.8,7.2-16,16-16h352c8.8,0,16,7.2,16,16V416z"></path></svg>`
        },
        'PPTX': {
            color: '#E67E22',
            bgColor: '#FAE5D3',
            svg: `<svg height="40px" width="40px" version="1.1" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><path style="fill:#E2E5E7;" d="M128,0c-17.6,0-32,14.4-32,32v448c0,17.6,14.4,32,32,32h320c17.6,0,32-14.4,32-32V128L352,0H128z"></path><path style="fill:#B0B7BD;" d="M384,128h96L352,0v96C352,113.6,366.4,128,384,128z"></path><polygon style="fill:#CAD1D8;" points="480,224 384,128 480,128"></polygon><path style="fill:#F15642;" d="M416,416c0,8.8-7.2,16-16,16H48c-8.8,0-16-7.2-16-16V256c0-8.8,7.2-16,16-16h352c8.8,0,16,7.2,16,16V416z"></path></svg>`
        },
        'TXT': {
            color: '#95A5A6',
            bgColor: '#ECF0F1',
            svg: `<svg height="40px" width="40px" version="1.1" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><path style="fill:#E2E5E7;" d="M128,0c-17.6,0-32,14.4-32,32v448c0,17.6,14.4,32,32,32h320c17.6,0,32-14.4,32-32V128L352,0H128z"></path><path style="fill:#B0B7BD;" d="M384,128h96L352,0v96C352,113.6,366.4,128,384,128z"></path><polygon style="fill:#CAD1D8;" points="480,224 384,128 480,128"></polygon><path style="fill:#576D7E;" d="M416,416c0,8.8-7.2,16-16,16H48c-8.8,0-16-7.2-16-16V256c0-8.8,7.2-16,16-16h352c8.8,0,16,7.2,16,16V416z"></path></svg>`
        },
        'ZIP': {
            color: '#8E44AD',
            bgColor: '#EBDEF0',
            svg: `<svg height="40px" width="40px" version="1.1" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><path style="fill:#E2E5E7;" d="M128,0c-17.6,0-32,14.4-32,32v448c0,17.6,14.4,32,32,32h320c17.6,0,32-14.4,32-32V128L352,0H128z"></path><path style="fill:#B0B7BD;" d="M384,128h96L352,0v96C352,113.6,366.4,128,384,128z"></path><polygon style="fill:#CAD1D8;" points="480,224 384,128 480,128"></polygon><path style="fill:#84BD5A;" d="M416,416c0,8.8-7.2,16-16,16H48c-8.8,0-16-7.2-16-16V256c0-8.8,7.2-16,16-16h352c8.8,0,16,7.2,16,16V416z"></path></svg>`
        }
    };

    const archivoInfo = tiposArchivo[extension] || {
        color: '#7F8C8D',
        bgColor: '#F8F9FA',
        svg: `<svg width="40" height="40" viewBox="0 0 24 24" fill="none"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" fill="#7F8C8D" opacity="0.2"/><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6z" stroke="#7F8C8D" stroke-width="2"/><path d="M14 2v6h6" stroke="#7F8C8D" stroke-width="2"/></svg>`
    };

    const mensajeHTML = `
        <div class="d-flex flex-column align-items-end mb-3">
            <div class="rounded p-0 bg-light" style="max-width: 400px; overflow: hidden; display: inline-block;">
                <a href="${documentUrl}" 
                   download="${originalName}"
                   class="documento-descarga"
                   style="
                       text-decoration: none; 
                       color: inherit; 
                       display: flex; 
                       align-items: center; 
                       gap: 14px;
                       padding: 12px 16px;
                       background: linear-gradient(135deg, ${archivoInfo.bgColor} 0%, #ffffff 100%);
                       transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                   "
                   onmouseover="
                       this.style.transform='translateX(4px)';
                       this.style.boxShadow='0 4px 12px rgba(0,0,0,0.08)';
                       this.querySelector('.download-icon').style.transform='translateY(2px)';
                       this.style.background='linear-gradient(135deg, ${archivoInfo.bgColor} 0%, #f8f9fa 100%)';
                   "
                   onmouseout="
                       this.style.transform='translateX(0)';
                       this.style.boxShadow='none';
                       this.querySelector('.download-icon').style.transform='translateY(0)';
                       this.style.background='linear-gradient(135deg, ${archivoInfo.bgColor} 0%, #ffffff 100%)';
                   ">
                    
                    <div style="
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        width: 48px;
                        height: 48px;
                        background: ${archivoInfo.color}15;
                        border-radius: 12px;
                        flex-shrink: 0;
                        box-shadow: 0 2px 8px ${archivoInfo.color}20;
                    ">
                        ${archivoInfo.svg}
                    </div>
                    
                    <div style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px;">
                        <div style="
                            font-weight: 600; 
                            font-size: 0.95rem; 
                            color: #2C3E50;
                            overflow: hidden;
                            text-overflow: ellipsis;
                            white-space: nowrap;
                        ">
                            ${originalName}
                        </div>
                        <div style="
                            display: flex;
                            align-items: center;
                            gap: 8px;
                            font-size: 0.8rem; 
                            color: #7F8C8D;
                            font-weight: 500;
                        ">
                            <span style="
                                background: ${archivoInfo.color};
                                color: white;
                                padding: 2px 8px;
                                border-radius: 4px;
                                font-size: 0.7rem;
                                font-weight: 600;
                            ">${extension}</span>
                            <span style="opacity: 0.8;">• Click para descargar</span>
                        </div>
                    </div>
                    
                    <div class="download-icon" style="
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        width: 36px;
                        height: 36px;
                        background: ${archivoInfo.color}10;
                        border-radius: 50%;
                        flex-shrink: 0;
                        transition: all 0.3s ease;
                    ">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="${archivoInfo.color}" stroke-width="2.5">
                            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                            <polyline points="7 10 12 15 17 10"></polyline>
                            <line x1="12" y1="15" x2="12" y2="3"></line>
                        </svg>
                    </div>
                </a>
            </div>
            <small class="text-muted me-2" style="margin-top: 4px;">${hora}</small>
        </div>
    `;

    chatMessages.insertAdjacentHTML('beforeend', mensajeHTML);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Función auxiliar para mostrar la imagen enviada inmediatamente en el chat
function agregarImagenEnviadaUI(fileUrl, caption) {
    const chatMessages = document.querySelector('.chat-messages');
    if (!chatMessages) return;

    const ahora = new Date();
    const hora = ahora.getHours().toString().padStart(2, '0') + ':' +
        ahora.getMinutes().toString().padStart(2, '0');

    // Detectar si es video por la extensión
    const esVideo = fileUrl.match(/\.(mp4|3gpp)$/i);

    let mediaHTML = '';
    if (esVideo) {
        mediaHTML = `
            <video controls style="width: 100%; max-width: 320px; border-radius: 8px;">
                <source src="${fileUrl}" type="video/mp4">
                Tu navegador no soporta el elemento de video.
            </video>
        `;
    } else {
        mediaHTML = `<img src="${fileUrl}" style="width: 100%; height: auto; display: block; border-radius: 8px;">`;
    }

    const mensajeHTML = `
        <div class="d-flex flex-column align-items-end mb-3">
            <div class="rounded p-0" style="max-width: 320px; overflow: hidden;">
                ${mediaHTML}
                ${caption ? `<div class="p-2 bg-light"><p class="mb-0" style="font-size: 0.9rem;">${caption}</p></div>` : ''}
            </div>
            <small class="text-muted me-2" style="margin-top: 4px;">${hora}</small>
        </div>
    `;

    chatMessages.insertAdjacentHTML('beforeend', mensajeHTML);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function enviarDocumentoWhatsApp(file, caption) {
    const formData = new FormData();
    formData.append('documento', file);
    formData.append('to', chatActivo.numero);
    formData.append('caption', caption);

    fetch('enviar_documento_whatsapp.php', { 
        method: 'POST', 
        body: formData 
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            agregarDocumentoEnviadoUI(data.document_url, data.original_name);
        } else {
            console.error('Error al enviar documento:', data.error);
        }
    })
    .catch(error => {
        console.error('Error de red:', error);
    });
}

function mostrarPreviewDocumento(file) {
    const extension = file.name.split('.').pop().toUpperCase();
    const sizeText = (file.size / 1024 / 1024).toFixed(2) + ' MB';
    
    const fileUrl = URL.createObjectURL(file);
    let previewHtml = '';

    if (file.type.startsWith('image/')) {
        previewHtml = `<img src="${fileUrl}" style="max-width: 100%; max-height: 200px; border-radius: 8px; margin-bottom: 10px;">`;
    } else if (file.type === 'application/pdf') {
        previewHtml = `<embed src="${fileUrl}#toolbar=0" type="application/pdf" width="100%" height="200px" style="border-radius: 8px; pointer-events: none;" />`;
    } else {
        previewHtml = `<div style="font-size: 60px; margin-bottom: 15px;">📄</div>`;
    }

    Swal.fire({
        title: 'Enviar documento',
        html: `
            <div style="background-color: #f0f2f5; border-radius: 12px; padding: 20px; text-align: center; border: 1px solid #e1e1e1;">
                <div id="file-preview-container" style="margin-bottom: 15px;">
                    ${previewHtml}
                </div>
                <div style="background: white; border-radius: 8px; padding: 10px; display: flex; align-items: center; text-align: left; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                    <div style="background: #02a698; color: white; padding: 10px; border-radius: 5px; margin-right: 12px; font-weight: bold; font-size: 12px;">
                        ${extension}
                    </div>
                    <div style="overflow: hidden;">
                        <div style="font-weight: 500; font-size: 14px; white-space: nowrap; text-overflow: ellipsis; overflow: hidden; color: #3b4a54;">${file.name}</div>
                        <div style="color: #667781; font-size: 12px;">${sizeText}</div>
                    </div>
                </div>
            </div>
            <input type="text" id="documentoCaption" class="swal2-input mx-0" 
                   placeholder="Escribe un mensaje..." style="width: 100%; margin-top: 20px; border-radius: 20px;">
        `,
        showCancelButton: true,
        confirmButtonText: 'Enviar',
        cancelButtonText: 'Cancelar',
        confirmButtonColor: '#25d366',
        cancelButtonColor: '#6c757d',
        width: '450px',
        focusConfirm: false,
        preConfirm: () => {
            return document.getElementById('documentoCaption').value;
        },
        didClose: () => {
            URL.revokeObjectURL(fileUrl); 
        }
    }).then((result) => {
        if (result.isConfirmed) {
            enviarDocumentoWhatsApp(file, result.value || '');
        } else {
            document.getElementById('inputDocumentoWhatsApp').value = '';
        }
    });
}

// ===============================================
// ENVIAR MENSAJE - AL CHAT ACTIVO
// ===============================================
function enviarMensajeWhatsApp() {
    const inputMensaje = document.querySelector('input[placeholder="Escribe un mensaje"]');
    const mensaje = inputMensaje.value.trim();

    if (!chatActivo.numero) {
        Swal.fire({
            icon: 'warning',
            title: 'No hay chat seleccionado',
            text: 'Selecciona un chat primero',
            timer: 2000,
            showConfirmButton: false
        });
        return;
    }

    if (!mensaje) return;

    // ✅ PAUSAR POLLING mientras se envía
    const pollingEstabaActivo = pollingActivo;
    if (pollingEstabaActivo) detenerPolling();

    fetch('enviar_whatsapp.php', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            to: chatActivo.numero,
            message: mensaje
        })
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                inputMensaje.value = '';

                // Agregar mensaje a la UI inmediatamente
                agregarMensajeEnviadoUI(data.texto_enviado || mensaje);

                // ✅ REANUDAR POLLING después de 2 segundos
                if (pollingEstabaActivo) {
                    setTimeout(() => iniciarPolling(), 2000);
                }
            } else {
                console.error('Error al enviar:', data.error?.message || 'Error desconocido');

                // ✅ REANUDAR POLLING inmediatamente si hay error
                if (pollingEstabaActivo) iniciarPolling();

                if (data.error?.ventana_expirada) {
                    Swal.fire({
                        icon: 'warning',
                        title: 'Ventana de 24h expirada',
                        text: 'Solo puedes enviar templates fuera de la ventana de 24h',
                        confirmButtonColor: '#25d366'
                    });
                }
            }
        })
        .catch(error => {
            console.error('Error de conexión:', error.message);
            // ✅ REANUDAR POLLING si hay error de conexión
            if (pollingEstabaActivo) iniciarPolling();
        });
}

// Función auxiliar para actualizar el preview en la lista de chats
function actualizarUltimoMensajeEnLista(numero, mensaje) {
    const chatItem = document.querySelector(`[data-numero="${numero}"]`);
    if (chatItem) {
        const ultimoMensajeElement = chatItem.querySelector('.text-truncate.text-muted');
        if (ultimoMensajeElement) {
            ultimoMensajeElement.textContent = mensaje;
            ultimoMensajeElement.classList.remove('text-muted');
            ultimoMensajeElement.classList.add('text-success');
        }
    }
}

// Función auxiliar para agregar mensaje a la UI de inmediato
function agregarMensajeEnviadoUI(texto) {
    const chatMessages = document.querySelector('.chat-messages');
    if (!chatMessages) return;

    const ahora = new Date();
    const hora = ahora.getHours().toString().padStart(2, '0') + ':' +
        ahora.getMinutes().toString().padStart(2, '0');

    const mensajeHTML = `
        <div class="d-flex flex-column align-items-end mb-3">
            <div class="p-2 rounded bg-light" style="min-width: 20%; max-width: 50%;">
                <p class="mb-0">${texto.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</p>
            </div>
            <small class="text-muted me-2">${hora}</small>
        </div>
    `;

    chatMessages.insertAdjacentHTML('beforeend', mensajeHTML);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function formatFileSize(bytes) {
    if (!bytes) return '';
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    if (bytes === 0) return '0 Bytes';
    const i = parseInt(Math.floor(Math.log(bytes) / Math.log(1024)));
    return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i];
}

document.addEventListener('DOMContentLoaded', function () {


    // Iniciar polling optimizado (reemplaza setInterval)
    iniciarPolling();

    const inputMensaje = document.querySelector('input[placeholder="Escribe un mensaje"]');
    if (inputMensaje) {
        inputMensaje.addEventListener('keypress', function (e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                enviarMensajeWhatsApp();
            }
        });
    }

    // Detener polling cuando la pestaña está oculta (ahorra recursos)
    document.addEventListener('visibilitychange', function () {
        if (document.hidden) {
            detenerPolling();
        } else {
            iniciarPolling();
        }
    });
});

async function disconnectWhatsApp() {
    logWhatsApp('=== INICIANDO DESCONEXIÓN DE WHATSAPP ===', 'INFO');

    // Confirmar con el usuario
    const confirmResult = await Swal.fire({
        title: '¿Desconectar WhatsApp?',
        text: 'Se desactivará la cuenta de WhatsApp. Tendrás que reconectar para enviar mensajes.',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#d33',
        cancelButtonColor: '#3085d6',
        confirmButtonText: 'Sí, desconectar',
        cancelButtonText: 'Cancelar'
    });

    if (!confirmResult.isConfirmed) {
        logWhatsApp('Desconexión cancelada por el usuario', 'INFO');
        return;
    }

    showWhatsAppLoader('Desconectando WhatsApp...');

    try {
        const response = await fetch('disconnect_whatsapp.php', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        const result = await response.json();

        hideWhatsAppLoader();

        if (result.success) {
            logWhatsApp('✓ Desconexión exitosa', 'SUCCESS');

            await Swal.fire({
                icon: 'success',
                title: 'Desconectado',
                text: 'WhatsApp ha sido desconectado exitosamente',
                timer: 2000
            });

            // Recargar página
            window.location.reload();

        } else {
            logWhatsApp('✗ Error al desconectar', 'ERROR');

            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: result.error || 'No se pudo desconectar WhatsApp'
            });
        }

    } catch (error) {
        logWhatsApp(`✗ Error en desconexión: ${error.message}`, 'ERROR');
        hideWhatsAppLoader();

        Swal.fire({
            icon: 'error',
            title: 'Error de conexión',
            text: 'No se pudo comunicar con el servidor'
        });
    }
}

// ===============================================
// MENÚ DE ADJUNTOS
// ===============================================
function toggleMenuAdjuntos() {
    const menu = document.getElementById('menuAdjuntos');
    
    if (menu.style.display === 'none' || menu.style.display === '') {
        menu.style.display = 'block';
        
        // Cerrar si se hace clic fuera
        setTimeout(() => {
            document.addEventListener('click', cerrarMenuAdjuntos);
        }, 100);
    } else {
        menu.style.display = 'none';
        document.removeEventListener('click', cerrarMenuAdjuntos);
    }
}

function cerrarMenuAdjuntos(event) {
    const menu = document.getElementById('menuAdjuntos');
    const btnAdjuntar = document.getElementById('btnAdjuntar');
    
    // Si el clic no fue en el menú ni en el botón, cerrar
    if (!menu.contains(event.target) && !btnAdjuntar.contains(event.target)) {
        menu.style.display = 'none';
        document.removeEventListener('click', cerrarMenuAdjuntos);
    }
}

// =============================================
// BÚSQUEDA DENTRO DEL CHAT 
// =============================================

let searchMatches = [];
let currentMatchIndex = -1;
let originalTexts = new Map();
let searchDebounceTimer = null;

/**
 * Abrir/cerrar barra de búsqueda
 */
function toggleChatSearch() {
    const bar = document.getElementById('chatSearchBar');
    if (bar.style.display === 'none' || bar.style.display === '') {
        bar.style.display = 'flex';
        document.getElementById('inputSearchChat').value = '';
        document.getElementById('inputSearchChat').focus();
    } else {
        closeChatSearch();
    }
}

/**
 * Cerrar búsqueda y limpiar todo
 */
function closeChatSearch() {
    const bar = document.getElementById('chatSearchBar');
    bar.style.display = 'none';
    document.getElementById('inputSearchChat').value = '';
    document.getElementById('searchResultsCount').textContent = '';
    clearHighlights();
    searchMatches = [];
    currentMatchIndex = -1;
}

/**
 * Buscar texto en los mensajes del chat visible
 */
function searchInChat(query) {
    // Debounce: esperar 300ms después de que deje de escribir
    clearTimeout(searchDebounceTimer);
    searchDebounceTimer = setTimeout(() => {
        ejecutarBusqueda(query);
    }, 300);
}

function ejecutarBusqueda(query) {
    clearHighlights();
    searchMatches = [];
    currentMatchIndex = -1;

    const countEl = document.getElementById('searchResultsCount');

    if (!query || query.trim().length < 2) {
        countEl.textContent = '';
        return;
    }

    const term = query.trim().toLowerCase();

    const chatContainer = document.querySelector('.chat-messages');
    if (!chatContainer) return;

    // Seleccionar TODOS los <p> dentro de las burbujas de mensaje
    const messageTextElements = chatContainer.querySelectorAll('.rounded.p-2 p');

    messageTextElements.forEach(el => {
        const text = el.textContent.toLowerCase();

        if (text.includes(term)) {
            // Guardar HTML original para poder restaurarlo
            if (!originalTexts.has(el)) {
                originalTexts.set(el, el.innerHTML);
            }

            // Reemplazar con spans de highlight
            el.innerHTML = highlightText(el.textContent, term);

            // Marcar la burbuja contenedora
            const burbuja = el.closest('.rounded.p-2');
            if (burbuja) burbuja.classList.add('msg-has-match');
        }
    });

    // Recopilar todos los spans resaltados
    searchMatches = Array.from(chatContainer.querySelectorAll('.search-highlight'));

    if (searchMatches.length > 0) {
        currentMatchIndex = 0;
        searchMatches[0].classList.add('active');
        searchMatches[0].scrollIntoView({ behavior: 'smooth', block: 'center' });
        countEl.textContent = `1 de ${searchMatches.length}`;
    } else {
        countEl.textContent = 'Sin resultados';
    }
}

/**
 * Resaltar coincidencias en el texto
 */
function highlightText(text, term) {
    const regex = new RegExp(`(${escapeRegex(term)})`, 'gi');
    return text.replace(regex, '<span class="search-highlight">$1</span>');
}

/**
 * Escapar caracteres especiales para regex
 */
function escapeRegex(string) {
    return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * Navegar entre resultados (flechas arriba/abajo)
 */
function navigateSearch(direction) {
    if (searchMatches.length === 0) return;

    // Quitar clase "active" del actual
    searchMatches[currentMatchIndex].classList.remove('active');

    if (direction === 'next') {
        currentMatchIndex = (currentMatchIndex + 1) % searchMatches.length;
    } else {
        currentMatchIndex = (currentMatchIndex - 1 + searchMatches.length) % searchMatches.length;
    }

    // Activar el nuevo y hacer scroll
    searchMatches[currentMatchIndex].classList.add('active');
    searchMatches[currentMatchIndex].scrollIntoView({ behavior: 'smooth', block: 'center' });

    document.getElementById('searchResultsCount').textContent =
        `${currentMatchIndex + 1} de ${searchMatches.length}`;
}

/**
 * Limpiar resaltados y restaurar texto original
 */
function clearHighlights() {
    originalTexts.forEach((html, el) => {
        if (el && el.parentNode) {
            el.innerHTML = html;
        }
    });
    originalTexts.clear();

    // Quitar clase de las burbujas
    document.querySelectorAll('.msg-has-match').forEach(el => {
        el.classList.remove('msg-has-match');
    });
}

// ===== ATAJOS DE TECLADO =====
document.addEventListener('keydown', function(e) {
    const chatPanel = document.getElementById('colChat');
    if (!chatPanel || chatPanel.style.display === 'none') return;

    // Ctrl+F → abrir búsqueda
    if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
        e.preventDefault();
        toggleChatSearch();
    }

    // Escape → cerrar búsqueda
    if (e.key === 'Escape') {
        const bar = document.getElementById('chatSearchBar');
        if (bar && bar.style.display === 'flex') {
            closeChatSearch();
        }
    }
});

// =============================================
// 📁 PANEL ARCHIVOS (solo 1 categoría a la vez)
// =============================================

function abrirPanelMedia(tipo) {
    const panel = document.getElementById('panelMediaFiles');
    const titulo = document.getElementById('panelMediaTitle');
    const contenido = document.getElementById('panelMediaContent');
    if (!panel || !titulo || !contenido) return;

    // Título según el botón presionado
    const titulos = {
        'multimedia': 'Archivos multimedia',
        'documentos': 'Documentos',
        'enlaces': 'Enlaces'
    };
    titulo.textContent = titulos[tipo] || '';

    // Cargar solo esa categoría
    contenido.innerHTML = '<div style="text-align:center; padding:40px; color:#8696A0;">Cargando...</div>';
    panel.style.display = 'block';

    // Pequeño delay para que se vea el panel antes de renderizar
    setTimeout(() => {
        cargarCategoria(tipo);
    }, 50);
}

function cerrarPanelMedia() {
    const panel = document.getElementById('panelMediaFiles');
    if (panel) panel.style.display = 'none';
}

function cargarCategoria(tipo) {
    if (!chatActivo.numero || !todasLasConversaciones[chatActivo.numero]) return;

    const mensajes = todasLasConversaciones[chatActivo.numero].mensajes;
    const contenido = document.getElementById('panelMediaContent');
    const urlRegex = /(https?:\/\/[^\s<>"{}|\\^`\[\]]+)/gi;

    if (tipo === 'multimedia') {
        const items = [];
        mensajes.forEach(msg => {
            if (msg.media_url && (msg.media_type === 'image' || msg.media_type === 'sticker')) {
                items.push({ type: 'image', url: msg.media_url, timestamp: msg.timestamp, fecha: msg.fecha });
            }
            if (msg.media_url && msg.media_type === 'video') {
                items.push({ type: 'video', url: msg.media_url, timestamp: msg.timestamp, fecha: msg.fecha });
            }
        });
        renderMultimedia(items, contenido);

    } else if (tipo === 'documentos') {
        const items = [];
        mensajes.forEach(msg => {
            if (msg.media_url && msg.media_type === 'document') {
                const filename = msg.filename || msg.media_url.split('/').pop() || 'documento';
                items.push({ url: msg.media_url, filename, extension: filename.split('.').pop().toUpperCase(), timestamp: msg.timestamp, fecha: msg.fecha });
            }
        });
        renderDocumentos(items, contenido);

    } else if (tipo === 'enlaces') {
        const items = [];
        mensajes.forEach(msg => {
            if (msg.texto) {
                const urls = msg.texto.match(urlRegex);
                if (urls) urls.forEach(url => items.push({ url, texto: msg.texto, timestamp: msg.timestamp, fecha: msg.fecha }));
            }
        });
        renderEnlaces(items, contenido);
    }
}

// =============================================
// AGRUPAR POR MES
// =============================================
function agruparPorMes(items) {
    const grupos = {};
    const meses = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'];

    items.forEach(item => {
        const fecha = item.timestamp ? new Date(item.timestamp * 1000) : new Date(item.fecha || Date.now());
        const ahora = new Date();
        let clave;

        if (fecha.getMonth() === ahora.getMonth() && fecha.getFullYear() === ahora.getFullYear()) {
            clave = 'ESTE MES';
        } else if (fecha.getFullYear() === ahora.getFullYear()) {
            clave = meses[fecha.getMonth()].toUpperCase();
        } else {
            clave = `${meses[fecha.getMonth()].toUpperCase()} ${fecha.getFullYear()}`;
        }

        if (!grupos[clave]) grupos[clave] = [];
        grupos[clave].push(item);
    });
    return grupos;
}

// =============================================
// RENDER: MULTIMEDIA
// =============================================
function renderMultimedia(items, container) {
    if (!items.length) {
        container.innerHTML = `
            <div class="media-empty">
                <svg width="50" height="50" viewBox="0 0 24 24" fill="none">
                    <rect x="3" y="3" width="18" height="18" rx="2" stroke="currentColor" stroke-width="1.5"/>
                    <circle cx="8.5" cy="8.5" r="1.5" stroke="currentColor" stroke-width="1.5"/>
                    <path d="M21 15l-5-5L5 21" stroke="currentColor" stroke-width="1.5"/>
                </svg>
                <p>No hay archivos multimedia</p>
            </div>`;
        return;
    }

    items.sort((a, b) => b.timestamp - a.timestamp);
    const grupos = agruparPorMes(items);
    let html = '';

    Object.keys(grupos).forEach(mes => {
        html += `<div class="media-group-title">${mes}</div><div class="media-grid">`;
        grupos[mes].forEach(item => {
            if (item.type === 'video') {
                html += `
                    <div class="media-grid-item" onclick="window.open('${item.url}','_blank')">
                        <video src="${item.url}" preload="metadata" muted></video>
                        <div class="media-video-badge">
                            <svg width="10" height="10" viewBox="0 0 24 24" fill="white"><path d="M8 5v14l11-7z"/></svg>
                        </div>
                    </div>`;
            } else {
                html += `
                    <div class="media-grid-item" onclick="window.open('${item.url}','_blank')">
                        <img src="${item.url}" alt="" loading="lazy">
                    </div>`;
            }
        });
        html += '</div>';
    });
    container.innerHTML = html;
}

// =============================================
// RENDER: DOCUMENTOS
// =============================================
function renderDocumentos(items, container) {
    if (!items.length) {
        container.innerHTML = `
            <div class="media-empty">
                <svg width="50" height="50" viewBox="0 0 24 24" fill="none">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" stroke="currentColor" stroke-width="1.5"/>
                    <path d="M14 2v6h6" stroke="currentColor" stroke-width="1.5"/>
                </svg>
                <p>No hay documentos</p>
            </div>`;
        return;
    }

    items.sort((a, b) => b.timestamp - a.timestamp);
    const grupos = agruparPorMes(items);
    const colores = { 'PDF':'#E74C3C','DOC':'#2E86DE','DOCX':'#2E86DE','XLS':'#27AE60','XLSX':'#27AE60','CSV':'#16A085','PPT':'#E67E22','PPTX':'#E67E22','TXT':'#95A5A6' };
    let html = '';

    Object.keys(grupos).forEach(mes => {
        html += `<div class="media-group-title">${mes}</div>`;
        grupos[mes].forEach(doc => {
            const color = colores[doc.extension] || '#7F8C8D';
            html += `
                <a href="${doc.url}" download="${doc.filename}" class="doc-list-item">
                    <div class="doc-icon" style="background:${color}15;">
                        <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" stroke="${color}" stroke-width="2"/>
                            <path d="M14 2v6h6" stroke="${color}" stroke-width="2"/>
                        </svg>
                    </div>
                    <div style="flex:1;min-width:0;">
                        <div class="doc-name">${doc.filename}</div>
                        <div class="doc-meta">
                            <span style="background:${color};color:#fff;padding:1px 6px;border-radius:3px;font-size:0.65rem;font-weight:600;">${doc.extension}</span>
                            <span style="margin-left:6px;">${doc.fecha || ''}</span>
                        </div>
                    </div>
                    <div style="flex-shrink:0;color:#8696A0;">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                            <polyline points="7 10 12 15 17 10"/>
                            <line x1="12" y1="15" x2="12" y2="3"/>
                        </svg>
                    </div>
                </a>`;
        });
    });
    container.innerHTML = html;
}

// =============================================
// RENDER: ENLACES
// =============================================
function renderEnlaces(items, container) {
    if (!items.length) {
        container.innerHTML = `
            <div class="media-empty">
                <svg width="50" height="50" viewBox="0 0 24 24" fill="none">
                    <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                    <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                </svg>
                <p>No hay enlaces compartidos</p>
            </div>`;
        return;
    }

    items.sort((a, b) => b.timestamp - a.timestamp);
    const grupos = agruparPorMes(items);
    let html = '';

    Object.keys(grupos).forEach(mes => {
        html += `<div class="media-group-title">${mes}</div>`;
        grupos[mes].forEach(link => {
            let domain = '';
            try { domain = new URL(link.url).hostname.replace('www.',''); } catch(e) { domain = link.url; }
            const textoLimpio = link.texto.replace(/(https?:\/\/[^\s]+)/gi,'').trim();

            html += `
                <a href="${link.url}" target="_blank" class="link-list-item">
                    <div class="link-preview-img">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                            <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                            <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                        </svg>
                    </div>
                    <div style="flex:1;min-width:0;">
                        ${textoLimpio ? `<div class="link-text">${textoLimpio}</div>` : ''}
                        <div class="link-url">${domain}</div>
                        <div style="color:#8696A0;font-size:0.7rem;margin-top:2px;">${link.fecha || ''}</div>
                    </div>
                </a>`;
        });
    });
    container.innerHTML = html;
}

// =============================================
// 🗑️ ELIMINAR CHAT
// =============================================

function confirmarEliminarChat() {
    if (!chatActivo.numero) return;
    document.getElementById('modalEliminarChat').style.display = 'block';
}

function cerrarModalEliminar() {
    document.getElementById('modalEliminarChat').style.display = 'none';
}

function ejecutarEliminarChat() {
    if (!chatActivo.numero) return;

    const btn = document.getElementById('btnConfirmarEliminar');
    btn.disabled = true;
    btn.textContent = 'Eliminando...';

    fetch('eliminar_chat.php', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            phone_number: chatActivo.numero
        })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        console.log('Respuesta del servidor:', data);
        
        // Restablecer botón SIEMPRE
        btn.disabled = false;
        btn.textContent = 'Sí, eliminar';
        cerrarModalEliminar();

        if (data.success) {
            try {
                // Guardar número antes de eliminarlo
                const numeroEliminado = chatActivo.numero;
                
                console.log('Eliminando conversación:', numeroEliminado);
                
                // Limpiar chat activo PRIMERO
                chatActivo.numero = null;
                
                // Eliminar del objeto local
                if (todasLasConversaciones && todasLasConversaciones[numeroEliminado]) {
                    delete todasLasConversaciones[numeroEliminado];
                    console.log('Conversación eliminada del objeto local');
                }
                
                // Cerrar panel de info
                const colInfo = document.getElementById('colInfo');
                if (colInfo) {
                    colInfo.classList.add('d-none');
                    colInfo.style.setProperty('display', 'none', 'important');
                }
                
                // Limpiar mensajes
                const chatMessages = document.querySelector('.chat-messages');
                if (chatMessages) {
                    chatMessages.innerHTML = '';
                }
                
                // Actualizar lista de chats (DEBE ejecutarse para ver el cambio)
                if (typeof actualizarListaChats === 'function') {
                    actualizarListaChats();
                    console.log('Lista de chats actualizada');
                } else {
                    console.error('actualizarListaChats no es una función');
                }
                
                // Verificar si quedan conversaciones
                const conversacionesRestantes = Object.keys(todasLasConversaciones || {});
                console.log('Conversaciones restantes:', conversacionesRestantes.length);
                
                if (conversacionesRestantes.length > 0) {
                    // Abrir el primer chat disponible
                    const primerChat = conversacionesRestantes[0];
                    console.log('Abriendo primer chat:', primerChat);
                    
                    if (typeof abrirChat === 'function') {
                        abrirChat(primerChat);
                    } else {
                        console.error('abrirChat no es una función');
                    }
                } else {
                    // No quedan chats - mostrar pantalla de bienvenida
                    console.log('No quedan chats, mostrando welcome screen');
                    
                    const colChat = document.getElementById('colChat');
                    const welcomeScreen = document.getElementById('welcomeScreen');
                    
                    if (colChat) {
                        colChat.style.setProperty('display', 'none', 'important');
                    }
                    if (welcomeScreen) {
                        welcomeScreen.style.setProperty('display', 'flex', 'important');
                    }
                }
                
                // Notificación de éxito
                if (typeof mostrarToast === 'function') {
                    mostrarToast('Chat eliminado correctamente', 'success');
                } else {
                    console.log('✅ Chat eliminado correctamente');
                }
                
            } catch (error) {
                console.error('Error al procesar eliminación en UI:', error);
                // Aunque falle el UI, el chat YA se eliminó del servidor
                // Recargar la página para sincronizar
                console.log('Recargando página para sincronizar...');
                setTimeout(() => {
                    location.reload();
                }, 1000);
            }
            
        } else {
            // El servidor dijo que falló
            console.error('El servidor reportó error:', data.message);
            if (typeof mostrarToast === 'function') {
                mostrarToast(data.message || 'Error al eliminar el chat', 'error');
            } else {
                alert(data.message || 'Error al eliminar el chat');
            }
        }
    })
    .catch(error => {
        console.error('Error en la petición:', error);
        
        // Restablecer botón
        btn.disabled = false;
        btn.textContent = 'Sí, eliminar';
        cerrarModalEliminar();
        
        if (typeof mostrarToast === 'function') {
            mostrarToast('Error de conexión al eliminar', 'error');
        } else {
            alert('Error de conexión al eliminar');
        }
    });
}

function mostrarToast(mensaje, tipo = 'success') {
    const toast = document.createElement('div');
    toast.style.cssText = `
        position:fixed; bottom:30px; left:50%; transform:translateX(-50%); 
        padding:12px 24px; border-radius:10px; color:#fff; font-size:0.88rem; font-weight:500;
        z-index:99999; box-shadow:0 4px 15px rgba(0,0,0,0.2);
        background:${tipo === 'success' ? '#10B981' : '#EF4444'};
        animation: toastIn 0.3s ease-out;
    `;
    toast.textContent = mensaje;
    document.body.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

function cargarPerfilWhatsApp() {
    // 1. Datos de BD
    fetch('leer_mensajes.php')
        .then(response => response.json())
        .then(data => {
            if (data.account_info) {
                document.getElementById('miNombrePerfil').textContent = data.account_info.business_name || 'Mi Negocio';
                document.getElementById('miNumeroPerfil').textContent = data.account_info.display_number || 'Sin número';
            }
        })
        .catch(error => console.error('Error BD:', error));

    // 2. Foto de perfil
    fetch('get_whatsapp_profile.php')
        .then(response => response.json())
        .then(data => {
            const foto = document.getElementById('miFotoPerfil');
            if (foto && data.data?.[0]?.profile_picture_url) {
                foto.src = data.data[0].profile_picture_url;
            }
        })
        .catch(error => console.error('Error foto:', error));
}

// Llamar al cargar
document.addEventListener('DOMContentLoaded', cargarPerfilWhatsApp);

// ══════════════════════════════════════
// GRABAR Y ENVIAR AUDIO (estilo WhatsApp)
// ══════════════════════════════════════
let mediaRecorder      = null;
let audioChunks        = [];
let grabacionTimer     = null;
let grabacionSegundos  = 0;
let grabacionPausada   = false;
let waveInterval       = null;

const btnGrabar = document.getElementById('btnGrabarAudio');
if (btnGrabar) {
    btnGrabar.addEventListener('click', iniciarGrabacion);
}

async function iniciarGrabacion() {
    if (!chatActivo.numero) return;

    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

        audioChunks    = [];
        grabacionPausada = false;

        const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
            ? 'audio/webm;codecs=opus'
            : MediaRecorder.isTypeSupported('audio/webm')
                ? 'audio/webm'
                : 'audio/ogg';

        mediaRecorder = new MediaRecorder(stream, { mimeType });

        mediaRecorder.ondataavailable = (e) => {
            if (e.data.size > 0) audioChunks.push(e.data);
        };

        mediaRecorder.onstop = () => {
            stream.getTracks().forEach(t => t.stop());
            if (grabacionSegundos >= 1 && !grabacionCancelada) {
                const blob = new Blob(audioChunks, { type: mimeType });
                enviarAudio(blob);
            }
            ocultarBarraGrabacion();
        };

        mediaRecorder.start(100); // chunks cada 100ms

        grabacionCancelada = false;
        grabacionSegundos  = 0;
        mostrarBarraGrabacion();
        iniciarTimerGrabacion();
        iniciarWaveAnimado();

    } catch (err) {
        alert('No se pudo acceder al micrófono: ' + err.message);
    }
}

let grabacionCancelada = false;

function mostrarBarraGrabacion() {
    // Ocultar caja normal de escritura
    document.querySelector('.d-flex.align-items-center.my-3.p-2').style.display = 'none';
    const barra = document.getElementById('barraGrabacion');
    barra.style.display = 'flex';
}

function ocultarBarraGrabacion() {
    document.querySelector('.d-flex.align-items-center.my-3.p-2').style.display = 'flex';
    document.getElementById('barraGrabacion').style.display = 'none';
    clearInterval(grabacionTimer);
    clearInterval(waveInterval);
}

function iniciarTimerGrabacion() {
    grabacionSegundos = 0;
    document.getElementById('grabTimer').textContent = '0:00';
    grabacionTimer = setInterval(() => {
        if (!grabacionPausada) {
            grabacionSegundos++;
            const m = Math.floor(grabacionSegundos / 60);
            const s = grabacionSegundos % 60;
            document.getElementById('grabTimer').textContent =
                m + ':' + (s < 10 ? '0' : '') + s;
        }
    }, 1000);
}

function iniciarWaveAnimado() {
    const container = document.getElementById('grabWave');
    container.innerHTML = '';
    const numBarras = 28;

    for (let i = 0; i < numBarras; i++) {
        const bar = document.createElement('div');
        bar.style.cssText = `
            width: 3px;
            height: 6px;
            background: var(--bs-primary);
            border-radius: 3px;
            transition: height 0.15s ease;
            opacity: 0.7;
        `;
        container.appendChild(bar);
    }

    const bars = container.querySelectorAll('div');
    waveInterval = setInterval(() => {
        if (grabacionPausada) return;
        bars.forEach(bar => {
            const h = Math.floor(Math.random() * 22) + 4;
            bar.style.height = h + 'px';
        });
    }, 120);
}

function pausarGrabacion() {
    if (!mediaRecorder) return;

    if (!grabacionPausada) {
        mediaRecorder.pause();
        grabacionPausada = true;
        document.getElementById('iconPausarGrab').style.display   = 'none';
        document.getElementById('iconReanudarGrab').style.display = 'block';
        document.getElementById('grabPunto').style.animationPlayState = 'paused';
        // Barras en reposo
        document.querySelectorAll('#grabWave div').forEach(b => b.style.height = '4px');
    } else {
        mediaRecorder.resume();
        grabacionPausada = false;
        document.getElementById('iconPausarGrab').style.display   = 'block';
        document.getElementById('iconReanudarGrab').style.display = 'none';
        document.getElementById('grabPunto').style.animationPlayState = 'running';
    }
}

function cancelarGrabacion() {
    grabacionCancelada = true;
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        mediaRecorder.stop();
    } else {
        ocultarBarraGrabacion();
    }
}

function detenerYEnviarGrabacion() {
    grabacionCancelada = false;
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        mediaRecorder.stop();
    }
}

async function enviarAudio(blob) {
    const numero = chatActivo.numero;

    // Preview optimista - mismo diseño que el player de audio
    const tempId   = 'temp-audio-' + Date.now();
    const numBarras = 30;
    const barras    = Array.from({ length: numBarras }, () => {
        const h = Math.floor(Math.random() * 16) + 8;
        return `<div style="flex:1; background:#D1D7DB; border-radius:2px; height:${h}px;"></div>`;
    }).join('');

    const chatMessages = document.querySelector('.chat-messages');
    chatMessages.insertAdjacentHTML('beforeend', `
        <div class="d-flex flex-column align-items-end mb-3" id="${tempId}">
            <div class="rounded p-2 bg-light" style="max-width:350px; padding:8px 12px; display:inline-block;">
                <div style="display:flex; align-items:center; gap:8px;">
                    <button disabled style="width:42px; height:42px; border-radius:50%; background:var(--bs-primary);
                            border:none; display:flex; align-items:center; justify-content:center;
                            flex-shrink:0; padding:0; opacity:0.7;">
                        <svg width="22" height="22" viewBox="0 0 24 24" fill="white">
                            <path d="M8 5v14l11-7z"/>
                        </svg>
                    </button>
                    <div style="flex:1; display:flex; align-items:center; gap:2px; height:32px;">${barras}</div>
                    <div style="color:#667781; font-size:0.75rem; min-width:35px; text-align:right;">0:00</div>
                </div>
            </div>
        </div>
    `);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    try {
        // Convertir webm → mp3
        const arrayBuffer = await blob.arrayBuffer();
        const audioCtx    = new AudioContext();
        const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);
        await audioCtx.close();

        const mp3Blob = await convertirAMp3(audioBuffer);

        const formData = new FormData();
        formData.append('audio', mp3Blob, 'audio_' + Date.now() + '.mp3');
        formData.append('to', numero);

        const data = await fetch('enviar_audio_whatsapp.php', {
            method: 'POST',
            body: formData
        }).then(r => r.json());

        document.getElementById(tempId)?.remove();

        if (data.success) {
            const ahora = new Date();
            const hora  = ahora.getHours() + ':' + String(ahora.getMinutes()).padStart(2, '0');

            if (todasLasConversaciones[numero]) {
                todasLasConversaciones[numero].mensajes.push({
                    tipo:       'enviado',
                    media_type: 'audio',
                    media_url:  '',
                    texto:      '[Audio]',
                    hora,
                    status:     'sent'
                });
            }

            mostrarMensajes(numero);
            actualizarListaChats();
        } else {
            alert('Error: ' + (data.error?.message || 'intenta de nuevo'));
        }

    } catch (err) {
        document.getElementById(tempId)?.remove();
        console.error('Error enviando audio:', err);
        alert('Error al procesar el audio: ' + err.message);
    }
}

function convertirAMp3(audioBuffer) {
    return new Promise((resolve) => {
        const sampleRate = audioBuffer.sampleRate;
        const channels   = audioBuffer.numberOfChannels;
        const mp3encoder = new lamejs.Mp3Encoder(channels, sampleRate, 128);

        const left     = audioBuffer.getChannelData(0);
        const right    = channels > 1 ? audioBuffer.getChannelData(1) : left;
        const leftInt  = Float32ToInt16(left);
        const rightInt = Float32ToInt16(right);

        const mp3Data  = [];
        const blockSize = 1152;

        for (let i = 0; i < leftInt.length; i += blockSize) {
            const leftChunk  = leftInt.subarray(i, i + blockSize);
            const rightChunk = rightInt.subarray(i, i + blockSize);
            const encoded    = mp3encoder.encodeBuffer(leftChunk, rightChunk);
            if (encoded.length > 0) mp3Data.push(new Int8Array(encoded));
        }

        const end = mp3encoder.flush();
        if (end.length > 0) mp3Data.push(new Int8Array(end));

        resolve(new Blob(mp3Data, { type: 'audio/mpeg' }));
    });
}

// ──────────────────────────────────────────────────────
//  CAMBIAR NÚMERO DE WHATSAPP
// ──────────────────────────────────────────────────────
async function cerrarSesionWhatsApp() {
    const btn = document.getElementById('btnCerrarSesionWA');
    const msg = document.getElementById('cambioNumeroMsg');

    const confirmado = await Swal.fire({
        title:              '¿Cerrar sesión de WhatsApp?',
        html:               'Se desconectará el número actual.<br><b>Deberás reiniciar Node.js y escanear el nuevo QR.</b>',
        icon:               'warning',
        showCancelButton:   true,
        confirmButtonColor: '#dc3545',
        cancelButtonColor:  '#6c757d',
        confirmButtonText:  'Sí, cerrar sesión',
        cancelButtonText:   'Cancelar'
    });

    if (!confirmado.isConfirmed) return;

    btn.disabled    = true;
    btn.textContent = 'Cerrando sesión...';
    if (msg) { msg.style.display = 'none'; }

    try {
        const resp = await fetch('/whatsapp/api/cambiar-numero/', {
            method:  'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') }
        });
        const data = await resp.json();

        if (data.success) {
            if (msg) {
                msg.style.display = 'block';
                msg.style.color   = '#198754';
                msg.innerHTML     = '✅ Sesión cerrada.<br>Ahora reinicia Node.js en la terminal y escanea el nuevo QR con tu nuevo número.';
            }
            Swal.fire('¡Listo!', 'Sesión cerrada. Reinicia Node.js (Ctrl+C → node index.js) y escanea el nuevo QR.', 'success');
        } else {
            throw new Error(data.error || 'Error desconocido');
        }
    } catch (e) {
        if (msg) {
            msg.style.display = 'block';
            msg.style.color   = '#dc3545';
            msg.textContent   = '❌ Error: ' + e.message;
        }
        btn.disabled    = false;
        btn.textContent = 'Cerrar sesión de WhatsApp';
    }
}

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        document.cookie.split(';').forEach(cookie => {
            cookie = cookie.trim();
            if (cookie.startsWith(name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
            }
        });
    }
    return cookieValue;
}

function Float32ToInt16(buffer) {
    const output = new Int16Array(buffer.length);
    for (let i = 0; i < buffer.length; i++) {
        const s    = Math.max(-1, Math.min(1, buffer[i]));
        output[i]  = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }
    return output;
}

// ── Almacén en memoria ──────────────────────────────────
const oportunidades = {};

const etapasConfig = {
    nuevo:        { label: 'Nuevo',             color: 'warning' },
    conversacion: { label: 'En conversación',   color: 'primary' },
    propuesta:    { label: 'Propuesta enviada', color: 'warning' },
    ganado:       { label: 'Ganado',            color: 'success' },
    perdido:      { label: 'Perdido',           color: 'danger'  }
};

// ── Abrir modal ─────────────────────────────────────────
function abrirModalOportunidad() {
    const numero = chatActivo.numero;
    if (!numero) return;

    const conv   = todasLasConversaciones[numero];
    const nombre = chatActivo.nombre || conv?.nombre || numero;
    const op     = oportunidades[numero];

    document.getElementById('oportunidadNombreContacto').textContent = nombre;
    document.getElementById('oportunidadNumeroContacto').textContent = numero;
    document.getElementById('oportunidadNotas').value = op?.notas || '';

    if (op) {
        document.getElementById('modalOportunidadTitulo').textContent  = 'Oportunidad activa';
        document.getElementById('campoEtapa').style.display            = 'block';
        document.getElementById('selectEtapa').value                   = op.etapa;
        document.getElementById('btnAccionOportunidad').textContent    = 'Guardar cambios';
    } else {
        document.getElementById('modalOportunidadTitulo').textContent  = 'Nueva Oportunidad';
        document.getElementById('campoEtapa').style.display            = 'none';
        document.getElementById('btnAccionOportunidad').textContent    = 'Crear oportunidad';
    }

    new bootstrap.Modal(document.getElementById('modalOportunidad')).show();
}

// ── Crear o actualizar ──────────────────────────────────
function guardarOportunidad() {
    const numero = chatActivo.numero;
    if (!numero) return;

    const conv   = todasLasConversaciones[numero];
    const notas  = document.getElementById('oportunidadNotas').value.trim();
    const existe = !!oportunidades[numero];

    if (existe) {
        oportunidades[numero].etapa     = document.getElementById('selectEtapa').value;
        oportunidades[numero].notas     = notas;
        oportunidades[numero].updatedAt = new Date().toISOString();
    } else {
        oportunidades[numero] = {
            id:          Date.now(),
            contactId:   numero,
            nombre:      chatActivo.nombre || conv?.nombre || numero,
            etapa:       'nuevo',
            notas:       notas,
            creadoEn:    new Date().toISOString(),
            updatedAt:   new Date().toISOString(),
            cerradoEn:   null
        };
    }

    bootstrap.Modal.getInstance(document.getElementById('modalOportunidad')).hide();
    actualizarBtnOportunidad(numero);
}

// ── Actualizar botón del panel ──────────────────────────
function actualizarBtnOportunidad(numero) {
    const op    = oportunidades[numero];
    const badge = document.getElementById('badgeEtapa');
    const texto = document.getElementById('textoOportunidad');

    const estilosBadge = {
        nuevo:        { bg: 'rgba(255, 193,  7, 0.15)', color: '#B45309', border: '1px solid rgba(255,193,7,0.4)'   },
        conversacion: { bg: 'rgba(var(--bs-primary-rgb), 0.12)', color: 'rgba(var(--bs-primary-rgb),1)', border: '1px solid rgba(var(--bs-primary-rgb),0.3)' },
        propuesta:    { bg: 'rgba(234, 88,  12, 0.12)', color: '#C2410C', border: '1px solid rgba(234,88,12,0.3)'   },
        ganado:       { bg: 'rgba(34,  197, 94, 0.12)', color: '#15803D', border: '1px solid rgba(34,197,94,0.3)'   },
        perdido:      { bg: 'rgba(239,  68, 68, 0.12)', color: '#B91C1C', border: '1px solid rgba(239,68,68,0.3)'   }
    };

    const emojis = {
        nuevo:        `<svg width="14" height="14" viewBox="0 0 24 24" fill="#F59E0B"><circle cx="12" cy="12" r="10"/></svg>`,
        conversacion: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>`,
        propuesta:    `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>`,
        ganado:       `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9H4a2 2 0 0 1-2-2V5a1 1 0 0 1 1-1h3"/><path d="M18 9h2a2 2 0 0 0 2-2V5a1 1 0 0 0-1-1h-3"/><path d="M12 17c-3.31 0-6-2.69-6-6V4h12v7c0 3.31-2.69 6-6 6z"/><path d="M12 17v4"/><path d="M8 21h8"/></svg>`,
        perdido:      `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>`
    };

    if (op) {
        const cfg  = etapasConfig[op.etapa];
        const estilo = estilosBadge[op.etapa];

        badge.innerHTML = `<span style="display:inline-flex; align-items:center; gap:5px;">${emojis[op.etapa]} ${cfg.label}</span>`;
        badge.style.cssText = `
            display: inline-block;
            font-size: 0.68rem;
            font-weight: 600;
            padding: 3px 10px;
            border-radius: 20px;
            letter-spacing: 0.3px;
            background: ${estilo.bg};
            color: ${estilo.color};
            border: ${estilo.border};
        `;
        if (texto) texto.textContent = 'Ver oportunidad';
    } else {
        badge.style.display = 'none';
        if (texto) texto.textContent = 'Oportunidad';
    }
}
