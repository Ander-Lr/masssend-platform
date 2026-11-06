// Polyfill crypto para Node.js < 19 (requerido por Baileys)
if (typeof globalThis.crypto === 'undefined') {
    const { webcrypto } = require('crypto');
    globalThis.crypto = webcrypto;
}

const { default: makeWASocket, useMultiFileAuthState, DisconnectReason, Browsers, fetchLatestBaileysVersion } = require('@whiskeysockets/baileys');
const { Boom } = require('@hapi/boom');
const express = require('express');
const qrcode = require('qrcode-terminal');
const P = require('pino');
const fs = require('fs');
const http = require('http');
const { createHmac } = require('crypto');
const { WebSocketServer } = require('ws');

const app = express();
app.use(express.json({ limit: '600mb' }));
app.use(express.urlencoded({ limit: '600mb', extended: true }));

// ─── Servidor HTTP + WebSocket (mismo puerto) ─────────────────────────
// Separación de responsabilidades: el servidor HTTP sirve la API REST,
// el WebSocketServer emite eventos en tiempo real (push) a los clientes React.
const server = http.createServer(app);
const wss = new WebSocketServer({ server });

// Broadcast: envía un mensaje a TODOS los clientes React conectados.
// Principio SRP: esta función solo tiene una responsabilidad — difundir eventos.
function broadcast(event, data) {
    const payload = JSON.stringify({ event, data, ts: Date.now() });
    wss.clients.forEach(client => {
        if (client.readyState === 1) { // 1 = OPEN
            client.send(payload);
        }
    });
}

wss.on('connection', (ws) => {
    console.log('[WS] Cliente React conectado. Total:', wss.clients.size);
    // Enviar estado actual al cliente recién conectado
    ws.send(JSON.stringify({
        event: 'status',
        data: { ready: isReady, has_qr: currentQR !== null, has_pairing: pairingCode !== null },
        ts: Date.now()
    }));
    ws.on('close', () => {
        console.log('[WS] Cliente React desconectado. Total:', wss.clients.size);
    });
});

// ─── Estado global ────────────────────────────────────────────────────
let isReady = false;
let currentQR = null;
let pairingCode = null;
let pairingPhone = null;
// Estado del socket: 'iniciando', 'esperando' (mostro un QR y acepta vincular),
// 'abierto' (vinculado) o 'cerrado' (esperando la reconexion programada).
let estadoConexion = 'cerrado';
let sock = null;
let reconnectTimer = null;

// ─── Cola de envío ────────────────────────────────────────────────────
const sendQueue = [];
let queueRunning = false;
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

// ─── Notificar a Django (webhooks firmados de la API v1) ───────────────
// Cada aviso lleva X-MassSend-Tiempo y X-MassSend-Firma: HMAC-SHA256 del
// texto "<tiempo>.<cuerpo>" con WHATSAPP_WEBHOOK_TOKEN. Django rechaza con
// 401 una firma inválida o un aviso de más de 5 minutos, así que un aviso
// capturado no se puede repetir ni alterar. Los webhooks son idempotentes:
// si Django no responde, se reintenta sin riesgo de duplicar nada.
const WEBHOOKS = {
    mensajes: '/api/v1/webhooks/whatsapp/mensajes',
    acuses: '/api/v1/webhooks/whatsapp/acuses',
    resultados: '/api/v1/webhooks/whatsapp/resultados',
};

function firmar(cuerpo, tiempo, secreto) {
    return 'sha256=' + createHmac('sha256', secreto).update(`${tiempo}.${cuerpo}`).digest('hex');
}

async function notifyDjango(path, body, intentos = 3) {
    const djangoUrl = (process.env.DJANGO_API_URL || 'http://localhost:8000').replace(/\/$/, '');
    const secreto = process.env.WHATSAPP_WEBHOOK_TOKEN || '';
    if (!secreto) {
        console.error('[Webhook] Falta WHATSAPP_WEBHOOK_TOKEN: Django rechazará el aviso.');
    }
    const cuerpo = JSON.stringify(body);
    for (let intento = 1; intento <= intentos; intento++) {
        const tiempo = Math.floor(Date.now() / 1000).toString();
        try {
            const resp = await fetch(`${djangoUrl}${path}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-MassSend-Tiempo': tiempo,
                    'X-MassSend-Firma': firmar(cuerpo, tiempo, secreto),
                },
                body: cuerpo,
            });
            // 4xx no se reintenta: el aviso está mal o la firma no coincide.
            if (resp.ok || (resp.status >= 400 && resp.status < 500)) {
                if (!resp.ok) console.error(`[Webhook] ${path} respondió ${resp.status}.`);
                return;
            }
        } catch (e) { /* Django no disponible: se reintenta */ }
        await sleep(1000 * intento);
    }
    console.error(`[Webhook] ${path} no respondió tras ${intentos} intentos.`);
}

// ─── Programar reconexión (única) ─────────────────────────────────────
function scheduleReconnect(delay = 5000) {
    if (reconnectTimer) return; // ya hay una reconexión programada
    console.log(`[WhatsApp] Reconectando en ${delay / 1000}s...`);
    reconnectTimer = setTimeout(async () => {
        reconnectTimer = null;
        await startClient();
    }, delay);
}

// Borra la sesion guardada. La carpeta es un volumen montado y no se puede eliminar:
// se borra su contenido, archivo por archivo.
function borrarCredenciales() {
    try {
        for (const f of fs.readdirSync('./auth_info_baileys')) {
            fs.rmSync(`./auth_info_baileys/${f}`, { recursive: true, force: true });
        }
    } catch (e) {
        console.error('[WhatsApp] No se pudieron borrar las credenciales:', e.message);
    }
}

// Reconecta ya, sin esperar la reconexion programada.
function reiniciarAhora() {
    if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
    }
    return startClient();
}

// Pide el codigo de vinculacion. Solo funciona con un socket que ya mostro un QR.
async function pedirCodigo() {
    const code = await sock.requestPairingCode(pairingPhone);
    pairingCode = code;
    currentQR = null;
    console.log(`[WhatsApp] Código de vinculación: ${code}`);
    return code;
}

// ─── Crear cliente WhatsApp (Baileys) ─────────────────────────────────
async function startClient() {
    estadoConexion = 'iniciando';
    // Un socket nuevo necesita su propio codigo: el anterior deja de servir.
    pairingCode = null;
    // Cerrar socket anterior si existe
    if (sock) {
        try { sock.end(new Error('Reiniciando')); } catch (_) {}
        sock = null;
    }

    try {
        // Obtener la versión más reciente de WhatsApp Web
        const { version } = await fetchLatestBaileysVersion();
        console.log(`[WhatsApp] Usando versión WA: ${version.join('.')}`);

        const { state, saveCreds } = await useMultiFileAuthState('./auth_info_baileys');

        sock = makeWASocket({
            version,
            auth: state,
            printQRInTerminal: false,
            logger: P({ level: 'silent' }),
            browser: ['MassSend', 'Chrome', '120.0.0.0'],
            connectTimeoutMs: 60000,
            defaultQueryTimeoutMs: 60000,
            retryRequestDelayMs: 2000,
        });

        // ─── Eventos de conexión ──────────────────────────────────────
        sock.ev.on('connection.update', async (update) => {
            const { connection, lastDisconnect, qr } = update;

            if (qr) {
                estadoConexion = 'esperando';
                isReady = false;
            }
            // Con un codigo ya pedido, WhatsApp sigue enviando QR: se ignoran.
            if (qr && !pairingCode) {
                currentQR = qr;
                console.log('====================================================');
                console.log('ESCANEA ESTE CODIGO QR CON TU WHATSAPP');
                console.log('====================================================');
                qrcode.generate(qr, { small: true });
                // Notificar a React via WebSocket: nuevo QR disponible
                broadcast('qr_update', { qr, ready: false });

                // Se pidio vincular mientras la conexion estaba cerrada: ahora si se puede.
                if (pairingPhone) {
                    try {
                        console.log(`[WhatsApp] Solicitando código de vinculación para ${pairingPhone}...`);
                        await pedirCodigo();
                    } catch (e) {
                        console.error('[WhatsApp] Error al pedir código:', e.message);
                    }
                }
            }

            if (connection === 'close') {
                estadoConexion = 'cerrado';
                isReady = false;
                const error = lastDisconnect?.error;
                const statusCode = (error instanceof Boom) ? error.output.statusCode : 0;

                // Log detallado del error real
                console.log(`[WhatsApp] Desconectado | código: ${statusCode} | motivo: ${error?.message || 'desconocido'}`);

                if (statusCode === DisconnectReason.loggedOut) {
                    console.log('[WhatsApp] Sesión cerrada. Borrando credenciales...');
                    borrarCredenciales();
                    scheduleReconnect(2000);
                } else if (statusCode === DisconnectReason.connectionReplaced) {
                    console.log('[WhatsApp] Conexión reemplazada por otra sesión.');
                    // No reconectar
                } else {
                    scheduleReconnect(5000);
                }
            }

            if (connection === 'open') {
                estadoConexion = 'abierto';
                isReady = true;
                currentQR = null;
                pairingCode = null;
                pairingPhone = null;
                console.log('[WhatsApp] Conectado exitosamente. Sistema listo.');
                // Notificar a React via WebSocket: WhatsApp conectado
                broadcast('wa_connected', { ready: true });
            }
        });

        sock.ev.on('creds.update', saveCreds);

        // ─── Mensajes ENTRANTES → Django ──────────────────────────────
        sock.ev.on('messages.upsert', async ({ messages, type }) => {
            if (type !== 'notify') return;
            for (const msg of messages) {
                if (msg.key.fromMe) continue;
                // Con LID el número real viene en senderPn, no en remoteJid
                const jid = msg.key.senderPn || msg.key.remoteJid || '';
                if (!jid.endsWith('@s.whatsapp.net')) continue;

                const number = jid.replace('@s.whatsapp.net', '');
                const body = msg.message?.conversation ||
                             msg.message?.extendedTextMessage?.text || '';
                if (!body) continue;

                console.log(`[WhatsApp] Mensaje entrante de ${number}: ${body.substring(0, 60)}`);
                await notifyDjango(WEBHOOKS.mensajes, { id: msg.key.id || null, telefono: number, texto: body });
                // Notificar a React via WebSocket: nuevo mensaje entrante (push instantáneo)
                // Esto reemplaza el polling cada 3s por un evento puntual y eficiente
                broadcast('new_message', { from: number, body, direction: 'inbound' });
            }
        });

        // ─── ACK de mensajes SALIENTES → Django ───────────────────────
        sock.ev.on('messages.update', async (updates) => {
            for (const update of updates) {
                if (!update.key?.fromMe) continue;
                const jid = update.key.remoteJid || '';
                if (!jid.endsWith('@s.whatsapp.net') && !jid.endsWith('@lid')) continue;

                const number = jid.split('@')[0];
                const statusNum = update.update?.status;
                if (!statusNum) continue;

                // WAMessageStatus: 2=SERVER_ACK, 3=DELIVERY_ACK, 4=READ, 5=PLAYED
                const statusMap = { 2: 'sent', 3: 'delivered', 4: 'read', 5: 'read' };
                const estadoV1 = { sent: 'enviado', delivered: 'entregado', read: 'leido' };
                const status = statusMap[statusNum];
                if (!status || !update.key.id) continue;

                await notifyDjango(WEBHOOKS.acuses, {
                    id_externo: update.key.id,
                    telefono: number,
                    estado: estadoV1[status],
                });
                // Notificar a React: estado del mensaje actualizado (ticks)
                broadcast('message_ack', { wpp_message_id: update.key.id, number, status });
            }
        });

    } catch (err) {
        console.error('[WhatsApp] Error al iniciar cliente:', err.message);
        scheduleReconnect(10000);
    }
}

// ─── Inicializar ──────────────────────────────────────────────────────
startClient();

// ─── Procesador de cola ───────────────────────────────────────────────
async function processSendQueue() {
    if (queueRunning) return;
    queueRunning = true;
    console.log('[Queue] Iniciando procesamiento de cola...');

    while (sendQueue.length > 0) {
        const task = sendQueue.shift();
        const { cleanNumber, message, media_base64, media_mimetype, media_filename, media_url, envio_id } = task;

        if (!isReady || !sock) {
            console.log(`[Queue] WhatsApp no listo. Esperando 5s antes de reintentar ${cleanNumber}...`);
            sendQueue.unshift(task);
            await sleep(5000);
            continue;
        }

        const jid = `${cleanNumber}@s.whatsapp.net`;

        try {
            let msgResult;

            if (media_base64 && media_mimetype) {
                const buffer = Buffer.from(media_base64, 'base64');
                if (media_mimetype.startsWith('image/')) {
                    msgResult = await sock.sendMessage(jid, {
                        image: buffer, caption: message || '',
                        mimetype: media_mimetype, fileName: media_filename || 'image'
                    });
                } else if (media_mimetype.startsWith('video/')) {
                    msgResult = await sock.sendMessage(jid, {
                        video: buffer, caption: message || '',
                        mimetype: media_mimetype, fileName: media_filename || 'video'
                    });
                } else {
                    msgResult = await sock.sendMessage(jid, {
                        document: buffer, caption: message || '',
                        mimetype: media_mimetype, fileName: media_filename || 'archivo'
                    });
                }
            } else if (media_url) {
                // Descarga el archivo (ej. desde PocketBase) y lo envía según
                // su tipo real: antes se mandaba todo como imagen y los videos
                // "se enviaban" pero nunca llegaban al destinatario.
                const resp = await fetch(media_url);
                if (!resp.ok) {
                    throw new Error(`No se pudo descargar el media (${resp.status}): ${media_url}`);
                }
                const buffer = Buffer.from(await resp.arrayBuffer());
                const mime = resp.headers.get('content-type') || 'application/octet-stream';
                if (mime.startsWith('image/')) {
                    msgResult = await sock.sendMessage(jid, {
                        image: buffer, caption: message || '', mimetype: mime
                    });
                } else if (mime.startsWith('video/')) {
                    msgResult = await sock.sendMessage(jid, {
                        video: buffer, caption: message || '', mimetype: mime
                    });
                } else {
                    msgResult = await sock.sendMessage(jid, {
                        document: buffer, caption: message || '',
                        mimetype: mime, fileName: media_url.split('/').pop() || 'archivo'
                    });
                }
            } else {
                msgResult = await sock.sendMessage(jid, { text: message });
            }

            const wppId = msgResult?.key?.id || null;
            console.log(`[Queue] ✓ Enviado a ${cleanNumber} | id=${wppId}`);
            // envio_id vuelve tal como llegó: así Django sabe a qué envío corresponde
            // sin adivinar por el número. Es null para los mensajes del chat.
            await notifyDjango(WEBHOOKS.resultados, {
                envio_id: envio_id || null, telefono: cleanNumber, estado: 'enviado', id_externo: wppId
            });
            // Push a React: mensaje de campaña enviado exitosamente
            broadcast('campaign_msg_sent', { number: cleanNumber, status: 'sent', wpp_message_id: wppId });

        } catch (err) {
            const errorMsg = err.message || String(err);
            console.error(`[Queue] ✗ Error enviando a ${cleanNumber}:`, errorMsg);
            await notifyDjango(WEBHOOKS.resultados, {
                envio_id: envio_id || null, telefono: cleanNumber, estado: 'fallido', error: errorMsg
            });
        }

        if (sendQueue.length > 0) {
            await sleep(2000);
        }
    }

    queueRunning = false;
    console.log('[Queue] Cola vaciada.');
}

// ─── Endpoints ────────────────────────────────────────────────────────

app.post('/api/send', (req, res) => {
    if (!isReady) {
        return res.status(503).json({ success: false, error: 'WhatsApp no conectado. Escanea el QR.' });
    }
    const { number, message, media_url, media_base64, media_mimetype, media_filename, envio_id } = req.body;
    if (!number || !(message || media_url || media_base64)) {
        return res.status(400).json({ success: false, error: 'Faltan parametros: number y message o media son requeridos.' });
    }
    const cleanNumber = number.replace(/[^0-9]/g, '');
    sendQueue.push({ cleanNumber, message, media_url, media_base64, media_mimetype, media_filename, envio_id });
    res.json({ success: true, status: 'queued', queue_size: sendQueue.length });
    processSendQueue();
});

app.get('/api/status', (req, res) => {
    res.json({ ready: isReady });
});

app.get('/api/qr', (req, res) => {
    res.json({
        ready: isReady,
        has_qr: currentQR !== null,
        qr: currentQR,
        has_pairing: pairingCode !== null,
        pairing_code: pairingCode,
        pairing_phone: pairingPhone
    });
});

app.post('/api/request-pairing', async (req, res) => {
    const { phone } = req.body;
    if (!phone) return res.status(400).json({ success: false, error: 'Falta el numero de telefono' });

    const cleanPhone = phone.replace(/[^0-9]/g, '');
    if (cleanPhone.length < 7) return res.status(400).json({ success: false, error: 'Numero invalido' });
    if (isReady) return res.status(400).json({ success: false, error: 'Ya hay un numero conectado.' });

    pairingPhone = cleanPhone;
    pairingCode = null;

    // Con un socket que muestra QR, el codigo sale al instante.
    if (sock && estadoConexion === 'esperando') {
        try {
            const code = await pedirCodigo();
            return res.json({ success: true, code });
        } catch (e) {
            console.error('[WhatsApp] El socket no acepto la vinculación, se reinicia:', e.message);
        }
    }

    // Conexion cerrada, reconectando o rechazada: se reconecta ya y el codigo se pide
    // en cuanto el socket nuevo este listo. El panel lo obtiene consultando el estado.
    if (estadoConexion !== 'iniciando') reiniciarAhora().catch(() => {});
    res.json({ success: true, message: 'El código se está generando. Aparecerá en unos segundos.' });
});

app.post('/api/logout', async (req, res) => {
    try {
        isReady = false;
        currentQR = null;
        pairingCode = null;
        pairingPhone = null;
        if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }

        res.json({ success: true, message: 'Desconectando...' });

        try { if (sock) await sock.logout(); } catch (e) {}
        // Borrar el contenido de la sesion es lo que realmente la invalida.
        borrarCredenciales();

        setTimeout(startClient, 2000);
    } catch (err) {
        if (!res.headersSent) res.status(500).json({ success: false, error: err.message });
    }
});

const PORT = process.env.PORT || 3001;
// Usar server.listen en lugar de app.listen para que HTTP y WebSocket
// compartan el mismo puerto — el servidor HTTP despacha las peticiones REST
// y el WebSocketServer maneja las conexiones WS en el mismo proceso.
server.listen(PORT, '0.0.0.0', () => {
    console.log(`[WhatsApp] API REST + WebSocket corriendo en http://0.0.0.0:${PORT}`);
    console.log(`[WhatsApp] WebSocket disponible en ws://0.0.0.0:${PORT}`);
    console.log('[WhatsApp] Iniciando WhatsApp (Baileys)...');
});
