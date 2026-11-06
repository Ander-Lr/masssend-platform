import { useEffect, useRef, useState } from 'react'
import { estadoAsistente, preguntar } from '../api/ia'
import Boton from '../components/ui/Boton'
import Insignia from '../components/ui/Insignia'
import { claseEntrada } from '../components/ui/Campo'

// Asistente de IA local con Ollama: la pregunta se procesa en el propio servidor.
const SUGERENCIAS = [
  '¿Cómo creo una campaña?',
  '¿Cuántos créditos tengo?',
  '¿Cómo importo mis contactos?',
  'Redáctame un mensaje para promocionar un descuento del 20%',
]
// Solo los ultimos turnos viajan como contexto: respuestas rapidas con un modelo pequeno.
const TURNOS_DE_CONTEXTO = 10

function EstadoModelo({ estado }) {
  if (!estado) return null
  const listo = estado.disponible && estado.modelo_descargado
  const color = listo ? 'verde' : estado.disponible ? 'amarilla' : 'roja'
  const texto = listo
    ? `Asistente listo · ${estado.modelo}`
    : estado.disponible ? `Falta descargar ${estado.modelo}` : 'Asistente no disponible'
  return <Insignia color={color} className="px-3 py-1.5 text-[0.78rem]">{texto}</Insignia>
}

export default function AsistentePage() {
  const [mensajes, setMensajes] = useState([])
  const [texto, setTexto] = useState('')
  const [cargando, setCargando] = useState(false)
  const [estado, setEstado] = useState(null)
  const [copiado, setCopiado] = useState(null)
  const scrollRef = useRef(null)

  useEffect(() => {
    estadoAsistente().then(setEstado).catch(() => setEstado({ disponible: false }))
  }, [])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [mensajes, cargando])

  const enviar = async sugerida => {
    const pregunta = (sugerida ?? texto).trim()
    if (!pregunta || cargando) return
    setTexto('')
    const historial = mensajes
      .filter(m => !m.error)
      .slice(-TURNOS_DE_CONTEXTO)
      .map(m => ({ rol: m.rol, contenido: m.contenido }))
    const conPregunta = [...mensajes, { rol: 'user', contenido: pregunta }]
    setMensajes(conPregunta)
    setCargando(true)
    try {
      const r = await preguntar(pregunta, historial)
      setMensajes([...conPregunta, { rol: 'assistant', contenido: r.respuesta, modelo: r.modelo, latencia: r.latencia_ms }])
    } catch (err) {
      setMensajes([...conPregunta, { rol: 'assistant', contenido: err.mensajeUsuario, error: true }])
    } finally {
      setCargando(false)
    }
  }

  const copiar = async (contenido, idx) => {
    try {
      await navigator.clipboard.writeText(contenido)
      setCopiado(idx)
      setTimeout(() => setCopiado(null), 1500)
    } catch { /* portapapeles no disponible */ }
  }

  return (
    <div className="flex flex-1 flex-col overflow-hidden bg-lienzo px-4 py-5 sm:px-8 sm:py-7">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-[1.4rem] font-bold">Asistente IA</h1>
          <p className="mt-1 text-[0.88rem] text-gray-500">
            Pregunta cómo usar MassSend o cuántos créditos tienes, o pide que la IA local (Ollama) te redacte un mensaje de campaña.
          </p>
        </div>
        <EstadoModelo estado={estado} />
      </div>

      <div ref={scrollRef} className="my-[18px] min-h-[200px] flex-1 overflow-y-auto rounded-xl border border-gray-200 bg-white p-[18px]">
        {mensajes.length === 0 && (
          <div className="mt-10 text-center">
            <p className="mb-4 font-semibold text-gray-500">¿En qué te puedo ayudar?</p>
            <div className="flex flex-wrap justify-center gap-2">
              {SUGERENCIAS.map(s => (
                <button key={s} onClick={() => enviar(s)}
                  className="rounded-full border-[1.5px] border-gray-200 bg-gray-50 px-3.5 py-2 text-[0.83rem] text-gray-700 transition-colors hover:border-marca">
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {mensajes.map((m, idx) => (
          <div key={idx} className={`mb-3 flex ${m.rol === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`inline-block max-w-[75%] whitespace-pre-wrap rounded-xl px-3.5 py-2.5 text-[0.9rem] leading-normal
              ${m.rol === 'user' ? 'bg-marca text-white' : m.error ? 'bg-red-100 text-red-700' : 'bg-gray-100 text-gray-800'}`}>
              {m.contenido}
              {m.rol === 'assistant' && !m.error && (
                <div className="mt-2 flex flex-wrap items-center gap-2.5 text-[0.72rem] text-gray-500">
                  <span>{m.latencia ? `${m.modelo} · ${m.latencia} ms` : m.modelo}</span>
                  {/* Solo los mensajes redactados por la IA tienen latencia: esos se copian a una campaña. */}
                  {m.latencia > 0 && (
                    <button onClick={() => copiar(m.contenido, idx)} className="p-0 font-bold text-blue-600">
                      {copiado === idx ? 'Copiado' : 'Copiar para tu campaña'}
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>
        ))}

        {cargando && (
          <div className="inline-block rounded-xl bg-gray-100 px-3.5 py-2.5 text-[0.9rem] text-gray-500">
            El modelo está pensando<span className="animate-pulse">...</span>
          </div>
        )}
      </div>

      <form onSubmit={e => { e.preventDefault(); enviar() }} className="flex gap-2.5">
        <input
          className={`${claseEntrada} flex-1 rounded-[10px] px-4 py-3`}
          value={texto}
          onChange={e => setTexto(e.target.value)}
          disabled={cargando}
          maxLength={5000}
          placeholder="Escribe tu pregunta o pide un mensaje para tu campaña..."
        />
        <Boton type="submit" tamano="lg" className="rounded-[10px]" disabled={cargando || !texto.trim()}>
          {cargando ? 'Esperando...' : 'Enviar'}
        </Boton>
      </form>
      <p className="mt-2 text-[0.74rem] text-gray-500">Las preguntas sobre MassSend se responden con la guía y tus datos. Los mensajes los redacta la IA: revísalos antes de usarlos.</p>
    </div>
  )
}
