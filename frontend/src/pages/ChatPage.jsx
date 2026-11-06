import { useCallback, useEffect, useRef, useState } from 'react'
import { sileo } from 'sileo'
import { enviarMensajeChat, fechaHora, listarConversaciones, listarMensajes } from '../api/envio'
import { useWhatsapp } from '../context/WhatsappContext'
import Insignia, { Punto } from '../components/ui/Insignia'
import { mostrarTelefono } from '../utils/telefono'

const INTERVALO_MS = 5000
const ESTADO_VISTO = {
  fallido: ['Falló', 'text-red-500'], leido: ['Leído', 'text-visto'], entregado: ['Entregado', 'text-gray-400'],
  pendiente: ['Pendiente', 'text-gray-400'], enviado: ['Enviado', 'text-gray-400'],
}
const iniciales = texto => (texto || '?').replace(/^\+/, '').slice(0, 2).toUpperCase()

function Avatar({ texto }) {
  return <div className="flex size-[46px] shrink-0 items-center justify-center rounded-full bg-burbuja text-[0.85rem] font-bold text-whatsapp">{iniciales(texto)}</div>
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
    <div className="flex h-full w-full flex-col md:flex-row">
      <div className="flex w-full flex-col overflow-hidden border-r border-gray-200 bg-white md:w-80">
        <div className="flex items-center justify-between border-b border-gray-200 p-4 text-[1.1rem] font-bold">
          Chats
          <Insignia color={conectado ? 'verde' : 'roja'}><Punto encendido={conectado} />{conectado ? 'Conectado' : 'Desconectado'}</Insignia>
        </div>
        <div className="border-b border-gray-200 px-4 py-2.5">
          <input placeholder="Buscar conversación..." value={busqueda} onChange={e => setBusqueda(e.target.value)}
            className="w-full rounded-full border border-gray-200 bg-lienzo px-3 py-2 text-[0.85rem] outline-none focus:border-marca" />
        </div>
        <div className="flex-1 overflow-y-auto">
          {visibles.length === 0 && <div className="p-6 text-center text-[0.9rem] text-gray-400">Sin conversaciones</div>}
          {visibles.map(c => (
            <div key={c.telefono} onClick={() => setActiva(c)} role="button" tabIndex={0} onKeyDown={e => { if (e.key === 'Enter') setActiva(c) }}
              className={`flex cursor-pointer items-center gap-3 border-b border-lienzo px-4 py-3 transition-colors ${activa?.telefono === c.telefono ? 'bg-green-50' : 'hover:bg-gray-50'}`}>
              <Avatar texto={c.nombre || c.telefono} />
              <div className="flex-1 overflow-hidden">
                <div className="truncate text-[0.9rem] font-semibold">{c.nombre || mostrarTelefono(c.telefono)}</div>
                <div className="mt-0.5 truncate text-[0.78rem] text-gray-400">{c.ultima_direccion === 'saliente' ? 'Tú: ' : ''}{c.ultimo_texto}</div>
              </div>
              <span className="shrink-0 rounded-full bg-purple-100 px-2 py-0.5 text-[0.7rem] text-violet-600">{c.mensajes}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="flex min-h-[420px] flex-1 flex-col bg-chat">
        {!activa ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-3 text-gray-400">
            <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="#ccc" strokeWidth="1.5" strokeLinecap="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" /></svg>
            <p>Selecciona una conversación</p>
          </div>
        ) : (
          <>
            <div className="flex shrink-0 items-center gap-3 border-b border-gray-200 bg-white px-5 py-3">
              <Avatar texto={activa.nombre || activa.telefono} />
              <div>
                <div className="font-bold">{activa.nombre || mostrarTelefono(activa.telefono)}</div>
                <div className="text-[0.78rem] text-gray-400">{mostrarTelefono(activa.telefono)}</div>
              </div>
            </div>
            <div ref={areaMensajes} className="flex flex-1 flex-col gap-1 overflow-y-auto px-6 py-4">
              {mensajes.length === 0 && (
                <p className="my-2 max-w-[420px] self-center rounded-lg bg-yellow-100 px-3.5 py-2 text-center text-[0.78rem] text-yellow-800">
                  Aquí aparecen los mensajes que tu cuenta intercambió con este número. Escribe para iniciar la conversación.
                </p>
              )}
              {mensajes.map(m => {
                const sale = m.direccion === 'saliente'
                const [visto, colorVisto] = ESTADO_VISTO[m.estado] || ESTADO_VISTO.enviado
                return (
                  <div key={m.id} className={`flex ${sale ? 'justify-end' : 'justify-start'}`}>
                    <div className={`max-w-[65%] whitespace-pre-wrap break-words rounded-lg px-3 py-2 text-[0.88rem] leading-snug ${sale ? 'rounded-br-sm bg-burbuja' : 'rounded-bl-sm bg-white'}`}>
                      {m.texto}
                      <div className="mt-0.5 text-right text-[0.68rem] text-gray-400">
                        {m.campana && <span className="mr-1.5">{m.campana} ·</span>}
                        {fechaHora(m.fecha)}
                        {sale && <span className={`ml-1 ${colorVisto}`}>{visto}</span>}
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
            <form className="flex shrink-0 items-center gap-2.5 bg-lienzo px-4 py-3" onSubmit={enviar}>
              <input value={texto} onChange={e => setTexto(e.target.value)} maxLength={4096} disabled={enviando}
                placeholder={conectado ? 'Escribe un mensaje' : 'WhatsApp está desconectado'}
                className="flex-1 rounded-3xl border-0 bg-white px-4 py-2.5 text-[0.9rem] outline-none" />
              <button type="submit" disabled={enviando || !texto.trim()} aria-label="Enviar"
                className="flex size-[42px] shrink-0 items-center justify-center rounded-full bg-marca text-white hover:bg-marca-oscuro disabled:bg-gray-400">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="#fff"><path d="M2 21l21-9L2 3v7l15 2-15 2z" /></svg>
              </button>
            </form>
          </>
        )}
      </div>
    </div>
  )
}
