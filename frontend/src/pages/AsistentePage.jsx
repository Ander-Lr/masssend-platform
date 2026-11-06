import { useEffect, useRef, useState } from 'react'
import { estadoAsistente, preguntar } from '../api/ia'

// Asistente de IA local con Ollama: la pregunta se procesa en el propio servidor.
const SUGERENCIAS = [
  '¿Cómo creo una campaña?',
  '¿Cómo importo mis contactos?',
  '¿Cómo funcionan los créditos?',
  'Redáctame un mensaje para promocionar un descuento del 20%',
]
// Solo los ultimos turnos viajan como contexto: respuestas rapidas con un modelo pequeno.
const TURNOS_DE_CONTEXTO = 10

function EstadoModelo({ estado }) {
  if (!estado) return null
  const listo = estado.disponible && estado.modelo_descargado
  const clase = listo ? 'insignia-verde' : estado.disponible ? 'insignia-amarilla' : 'insignia-roja'
  const texto = listo
    ? `Asistente listo · ${estado.modelo}`
    : estado.disponible ? `Falta descargar ${estado.modelo}` : 'Asistente no disponible'
  return <span className={`insignia ${clase}`} style={{ padding: '6px 12px', fontSize: '0.78rem' }}>{texto}</span>
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
    <div className="pagina" style={{ display: 'flex', flexDirection: 'column' }}>
      <div className="pagina-encabezado" style={{ marginBottom: 0 }}>
        <div>
          <h1 className="pagina-titulo">Asistente IA</h1>
          <p className="pagina-subtitulo">
            Modelo de IA local ejecutado con Ollama. Pregunta cómo usar MassSend o pide que te redacte un mensaje de campaña.
          </p>
        </div>
        <EstadoModelo estado={estado} />
      </div>

      <div ref={scrollRef} className="tarjeta" style={{ flex: 1, overflowY: 'auto', margin: '18px 0', padding: 18, minHeight: 200 }}>
        {mensajes.length === 0 && (
          <div style={{ textAlign: 'center', marginTop: 40 }}>
            <p style={{ fontWeight: 600, marginBottom: 16, color: '#6b7280' }}>¿En qué te puedo ayudar?</p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'center' }}>
              {SUGERENCIAS.map(s => (
                <button key={s} className="sugerencia" onClick={() => enviar(s)}>{s}</button>
              ))}
            </div>
          </div>
        )}

        {mensajes.map((m, idx) => (
          <div key={idx} style={{ display: 'flex', justifyContent: m.rol === 'user' ? 'flex-end' : 'flex-start', marginBottom: 12 }}>
            <div className={`burbuja-ia ${m.rol === 'user' ? 'usuario' : m.error ? 'error' : ''}`}>
              {m.contenido}
              {m.rol === 'assistant' && !m.error && (
                <div className="burbuja-pie">
                  <span>{m.modelo} · {m.latencia} ms</span>
                  <button onClick={() => copiar(m.contenido, idx)}>
                    {copiado === idx ? 'Copiado' : 'Copiar para tu campaña'}
                  </button>
                </div>
              )}
            </div>
          </div>
        ))}

        {cargando && (
          <div className="burbuja-ia" style={{ color: '#6b7280' }}>
            El modelo está pensando<span style={{ animation: 'pulse 1s infinite' }}>...</span>
          </div>
        )}
      </div>

      <form onSubmit={e => { e.preventDefault(); enviar() }} style={{ display: 'flex', gap: 10 }}>
        <input
          className="entrada"
          value={texto}
          onChange={e => setTexto(e.target.value)}
          disabled={cargando}
          maxLength={5000}
          placeholder="Escribe tu pregunta o pide un mensaje para tu campaña..."
          style={{ flex: 1, padding: '12px 16px', borderRadius: 10 }}
        />
        <button type="submit" className="boton boton-primario" disabled={cargando || !texto.trim()} style={{ padding: '12px 22px', borderRadius: 10 }}>
          {cargando ? 'Esperando...' : 'Enviar'}
        </button>
      </form>
      <p className="texto-suave" style={{ fontSize: '0.74rem', marginTop: 8 }}>
        El modelo es pequeño y puede equivocarse. Revisa sus respuestas antes de usarlas.
      </p>
    </div>
  )
}
