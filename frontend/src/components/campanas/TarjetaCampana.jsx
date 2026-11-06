import { useEffect, useState } from 'react'
import { ESTADOS, progresoCampana } from '../../api/campanas'
import Etiquetas from '../ui/Etiquetas'

const INTERVALO_MS = 3000

function Spinner() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" className="girando" aria-hidden="true">
      <path d="M21 12a9 9 0 1 1-6.219-8.56" />
    </svg>
  )
}

// Consulta el avance; mientras la campana esta en curso lo actualiza cada 3 segundos.
function useProgreso(campana, onTermino) {
  const [progreso, setProgreso] = useState(null)
  const enCurso = campana.estado === 'en_curso'
  const conEnvios = campana.estado !== 'borrador'

  useEffect(() => {
    if (!conEnvios) return undefined
    let vigente = true
    let temporizador = null
    const consultar = async () => {
      try {
        const p = await progresoCampana(campana.id)
        if (!vigente) return
        setProgreso(p)
        if (enCurso && p.estado !== 'en_curso') { onTermino?.(p); return }
      } catch { /* se reintenta en el siguiente ciclo */ }
      if (vigente && enCurso) temporizador = setTimeout(consultar, INTERVALO_MS)
    }
    consultar()
    return () => { vigente = false; clearTimeout(temporizador) }
  }, [campana.id, enCurso, conEnvios, onTermino])

  return progreso
}

function BarraProgreso({ p, enCurso }) {
  return (
    <div style={{ marginTop: 10 }}>
      <div className="progreso-datos">
        <span>Total: <strong>{p.total}</strong></span>
        <span style={{ color: '#10b981' }}>Enviados: <strong>{p.enviados}</strong></span>
        <span style={{ color: '#ef4444' }}>Fallidos: <strong>{p.fallidos}</strong></span>
        {p.omitidos > 0 && <span style={{ color: '#6b7280' }}>Omitidos: <strong>{p.omitidos}</strong></span>}
        {p.cancelados > 0 && <span style={{ color: '#6b7280' }}>Cancelados: <strong>{p.cancelados}</strong></span>}
        {enCurso && <span style={{ color: '#92400e' }}>Pendientes: <strong>{p.pendientes}</strong></span>}
        <span style={{ fontWeight: 700, color: enCurso ? '#92400e' : '#374151' }}>{p.porcentaje}%</span>
      </div>
      <div className="progreso-pista">
        <div className={`progreso-relleno${enCurso ? ' activo' : ''}`} style={{ width: `${p.porcentaje}%` }} />
      </div>
      {enCurso && (
        <p style={{ fontSize: '0.7rem', color: '#92400e', marginTop: 5, fontWeight: 500 }}>
          Enviando mensajes con pausas para cuidar tu número de WhatsApp. Se actualiza cada 3 segundos.
        </p>
      )}
    </div>
  )
}

export default function TarjetaCampana({ campana, onLanzar, onEditar, onEliminar, onCancelar, onTermino, ocupada }) {
  const estado = ESTADOS[campana.estado] || ESTADOS.borrador
  const enCurso = campana.estado === 'en_curso'
  const progreso = useProgreso(campana, onTermino)

  return (
    <div className={`tarjeta-campana${enCurso ? ' en-curso' : ''}`}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12, flexWrap: 'wrap' }}>
        <div style={{ flex: 1, minWidth: 240 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6, flexWrap: 'wrap' }}>
            <span style={{ fontWeight: 700, fontSize: '0.95rem' }}>{campana.nombre}</span>
            <span className={`insignia insignia-${estado.clase}`}>{estado.label}</span>
            {enCurso && <span className="ejecutando"><Spinner /> Enviando...</span>}
            {campana.tiene_adjunto && <span className="insignia insignia-gris">Con adjunto</span>}
            <Etiquetas lista={campana.etiquetas} vacio="Todos los contactos" />
          </div>
          <p className="mensaje-campana">{campana.mensaje}</p>
          {progreso && progreso.total > 0 && <BarraProgreso p={progreso} enCurso={enCurso} />}
        </div>

        <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
          {campana.estado === 'borrador' && (
            <>
              <button className="boton-accion violeta" disabled={ocupada} onClick={() => onLanzar(campana)}>
                {ocupada ? <><Spinner /> Lanzando...</> : 'Lanzar'}
              </button>
              <button className="boton-accion gris" onClick={() => onEditar(campana)}>Editar</button>
            </>
          )}
          {enCurso && (
            <button className="boton-accion rojo" disabled={ocupada} onClick={() => onCancelar(campana)}>
              {ocupada ? 'Cancelando...' : 'Cancelar envío'}
            </button>
          )}
          {!enCurso && <button className="boton-accion rojo" onClick={() => onEliminar(campana)}>Eliminar</button>}
        </div>
      </div>
    </div>
  )
}
