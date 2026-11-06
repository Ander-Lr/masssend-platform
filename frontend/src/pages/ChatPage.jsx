import { useCallback, useEffect, useRef, useState } from 'react'
import { sileo } from 'sileo'
import { enviarMensajeChat, fechaHora, listarConversaciones, listarMensajes } from '../api/envio'
import { useWhatsapp } from '../context/WhatsappContext'
import { mostrarTelefono } from '../utils/telefono'

const INTERVALO_MS = 5000
const iniciales = texto => (texto || '?').replace(/^\+/, '').slice(0, 2).toUpperCase()

function Avatar({ texto }) {
  return <div className="chat-avatar avatar-texto">{iniciales(texto)}</div>
}

// Chat del panel con el numero de la plataforma. Solo staff; no consume creditos.
export default function ChatPage() {
  const { conectado } = useWhatsapp()
  const [conversaciones, setConversaciones] = useState([])
  const [busqueda, setBusqueda] = useState('')
  const [activa, setActiva] = useState(null)
  const [mensajes, setMensajes] = useState([])
  const [texto, setTexto] = useState('')
  const [enviando, setEnviando] = useState(false)
  const areaMensajes = useRef(null)

  // Conversaciones y mensajes se refrescan cada 5 segundos para ver las respuestas.
  useEffect(() => {
    let vigente = true
    const cargar = () => listarConversaciones().then(r => vigente && setConversaciones(r.datos)).catch(() => {})
    cargar()
    const t = setInterval(cargar, INTERVALO_MS)
    return () => { vigente = false; clearInterval(t) }
  }, [])

  const cargarMensajes = useCallback(telefono =>
    listarMensajes({ telefono, limite: 100 }).then(r => r.datos.slice().reverse()), [])

  useEffect(() => {
    if (!activa) return undefined
    let vigente = true
    const cargar = () => cargarMensajes(activa.telefono).then(lista => vigente && setMensajes(lista)).catch(() => {})
    cargar()
    const t = setInterval(cargar, INTERVALO_MS)
    return () => { vigente = false; clearInterval(t) }
  }, [activa, cargarMensajes])

  useEffect(() => {
    areaMensajes.current?.scrollTo({ top: areaMensajes.current.scrollHeight })
  }, [mensajes])

  const enviar = async e => {
    e.preventDefault()
    const contenido = texto.trim()
    if (!contenido || !activa) return
    setEnviando(true)
    try {
      const r = await enviarMensajeChat(activa.telefono, contenido)
      setTexto('')
      if (r.estado === 'fallido') sileo.error({ title: 'No se pudo enviar', description: r.detalle })
      setMensajes(await cargarMensajes(activa.telefono))
    } catch (err) {
      sileo.error({ title: 'No se pudo enviar', description: err.mensajeUsuario })
    } finally {
      setEnviando(false)
    }
  }

  const filtro = busqueda.trim().toLowerCase()
  const visibles = conversaciones.filter(c => !filtro || c.telefono.includes(filtro) || c.nombre?.toLowerCase().includes(filtro))

  return (
    <div className="chat-page">
      <div className="chat-list">
        <div className="chat-list-header">
          Chats
          <span className={`wa-badge ${conectado ? 'connected' : 'disconnected'}`}>
            <span className={`wa-dot ${conectado ? 'on' : 'off'}`} />{conectado ? 'Conectado' : 'Desconectado'}
          </span>
        </div>
        <div className="chat-search">
          <input placeholder="Buscar conversación..." value={busqueda} onChange={e => setBusqueda(e.target.value)} />
        </div>
        <div className="chat-items">
          {visibles.length === 0 && <div className="loading" style={{ padding: 24 }}>Sin conversaciones</div>}
          {visibles.map(c => (
            <div key={c.telefono} className={`chat-item${activa?.telefono === c.telefono ? ' active' : ''}`} onClick={() => setActiva(c)}
              role="button" tabIndex={0} onKeyDown={e => { if (e.key === 'Enter') setActiva(c) }}>
              <Avatar texto={c.nombre || c.telefono} />
              <div className="chat-info">
                <div className="chat-name">{c.nombre || mostrarTelefono(c.telefono)}</div>
                <div className="chat-preview">{c.ultima_direccion === 'saliente' ? 'Tú: ' : ''}{c.ultimo_texto}</div>
              </div>
              <span className="chat-tag">{c.mensajes}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="chat-window">
        {!activa ? (
          <div className="empty-chat">
            <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="#ccc" strokeWidth="1.5" strokeLinecap="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" /></svg>
            <p>Selecciona una conversación</p>
          </div>
        ) : (
          <>
            <div className="chat-window-header">
              <Avatar texto={activa.nombre || activa.telefono} />
              <div>
                <div className="chat-window-name">{activa.nombre || mostrarTelefono(activa.telefono)}</div>
                <div className="chat-window-num">{mostrarTelefono(activa.telefono)}</div>
              </div>
            </div>
            <div className="messages-area" ref={areaMensajes}>
              {mensajes.length === 0 && (
                <p className="aviso-chat">Aquí aparecen los mensajes que tu cuenta intercambió con este número. Escribe para iniciar la conversación.</p>
              )}
              {mensajes.map(m => {
                const sale = m.direccion === 'saliente'
                return (
                  <div key={m.id} className={`bubble-row ${sale ? 'out' : 'in'}`}>
                    <div className={`bubble ${sale ? 'out' : 'in'}`} style={{ whiteSpace: 'pre-wrap' }}>
                      {m.texto}
                      <div className="bubble-time">
                        {m.campana && <span style={{ marginRight: 6 }}>{m.campana} ·</span>}
                        {fechaHora(m.fecha)}
                        {sale && <span className="bubble-status" style={{ marginLeft: 4, color: m.estado === 'fallido' ? '#ef4444' : m.estado === 'leido' ? '#53bdeb' : '#9ca3af' }}>{m.estado === 'fallido' ? 'Falló' : m.estado === 'leido' ? 'Leído' : m.estado === 'entregado' ? 'Entregado' : m.estado === 'pendiente' ? 'Pendiente' : 'Enviado'}</span>}
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
            <form className="chat-input-area" onSubmit={enviar}>
              <input className="chat-input" value={texto} onChange={e => setTexto(e.target.value)} maxLength={4096}
                placeholder={conectado ? 'Escribe un mensaje' : 'WhatsApp está desconectado'} disabled={enviando} />
              <button className="send-btn" type="submit" disabled={enviando || !texto.trim()} aria-label="Enviar">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="#fff"><path d="M2 21l21-9L2 3v7l15 2-15 2z" /></svg>
              </button>
            </form>
          </>
        )}
      </div>
    </div>
  )
}
