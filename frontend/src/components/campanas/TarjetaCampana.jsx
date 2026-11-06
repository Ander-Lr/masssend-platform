import { useEffect, useState } from 'react'
import { ESTADOS, progresoCampana } from '../../api/campanas'
import Etiquetas from '../ui/Etiquetas'
import Insignia from '../ui/Insignia'
import Progreso, { Spinner } from '../ui/Progreso'
import { BotonMini } from '../ui/Boton'

const INTERVALO_MS = 3000

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
    <div className="mt-2.5">
      <div className="mb-1.5 flex flex-wrap gap-4 text-[0.75rem] text-gray-600">
        <span>Total: <strong>{p.total}</strong></span>
        <span className="text-emerald-500">Enviados: <strong>{p.enviados}</strong></span>
        <span className="text-red-500">Fallidos: <strong>{p.fallidos}</strong></span>
        {p.omitidos > 0 && <span className="text-gray-500">Omitidos: <strong>{p.omitidos}</strong></span>}
        {p.cancelados > 0 && <span className="text-gray-500">Cancelados: <strong>{p.cancelados}</strong></span>}
        {enCurso && <span className="text-amber-800">Pendientes: <strong>{p.pendientes}</strong></span>}
        <span className={`font-bold ${enCurso ? 'text-amber-800' : 'text-gray-700'}`}>{p.porcentaje}%</span>
      </div>
      <Progreso porcentaje={p.porcentaje} activo={enCurso} />
      {enCurso && (
        <p className="mt-1.5 text-[0.7rem] font-medium text-amber-800">
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
    <div className={`rounded-xl border-l-4 bg-white px-5 py-[18px] shadow-[0_1px_3px_rgba(0,0,0,0.06)] transition-colors ${enCurso ? 'border-amber-500' : 'border-transparent'}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-60 flex-1">
          <div className="mb-1.5 flex flex-wrap items-center gap-2.5">
            <span className="text-[0.95rem] font-bold">{campana.nombre}</span>
            <Insignia color={estado.clase}>{estado.label}</Insignia>
            {enCurso && <span className="inline-flex items-center gap-1.5 text-[0.72rem] font-semibold text-amber-800"><Spinner /> Enviando...</span>}
            {campana.tiene_adjunto && <Insignia>Con adjunto</Insignia>}
            <Etiquetas lista={campana.etiquetas} vacio="Todos los contactos" />
          </div>
          <p className="line-clamp-2 whitespace-pre-wrap text-[0.8rem] text-gray-400">{campana.mensaje}</p>
          {progreso && progreso.total > 0 && <BarraProgreso p={progreso} enCurso={enCurso} />}
        </div>

        <div className="flex shrink-0 gap-2">
          {campana.estado === 'borrador' && (
            <>
              <BotonMini grande color="indigo" disabled={ocupada} onClick={() => onLanzar(campana)}>
                {ocupada ? <><Spinner /> Lanzando...</> : 'Lanzar'}
              </BotonMini>
              <BotonMini grande onClick={() => onEditar(campana)}>Editar</BotonMini>
            </>
          )}
          {enCurso && (
            <BotonMini grande color="rojo" disabled={ocupada} onClick={() => onCancelar(campana)}>
              {ocupada ? 'Cancelando...' : 'Cancelar envío'}
            </BotonMini>
          )}
          {!enCurso && <BotonMini grande color="rojo" onClick={() => onEliminar(campana)}>Eliminar</BotonMini>}
        </div>
      </div>
    </div>
  )
}
