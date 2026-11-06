import { useCallback, useEffect, useState } from 'react'
import { sileo } from 'sileo'
import AlertBox from '../components/auth/AlertBox'
import { confirmar } from '../components/ui/confirmar'
import FormularioCampana from '../components/campanas/FormularioCampana'
import ConfirmarLanzamiento from '../components/campanas/ConfirmarLanzamiento'
import TarjetaCampana from '../components/campanas/TarjetaCampana'
import { ESTADOS, cancelarCampana, eliminarCampana, lanzarCampana, listarCampanas } from '../api/campanas'

const PESTANAS = [{ valor: '', label: 'Todas' }, ...Object.entries(ESTADOS).map(([valor, e]) => ({ valor, label: e.label }))]

const duracion = segundos => {
  if (segundos < 60) return `${segundos} s`
  const minutos = Math.round(segundos / 60)
  return minutos < 60 ? `${minutos} min` : `${Math.floor(minutos / 60)} h ${minutos % 60} min`
}

export default function CampanasPage() {
  const [campanas, setCampanas] = useState([])
  const [estado, setEstado] = useState('')
  const [cursor, setCursor] = useState(null)
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState('')
  const [formulario, setFormulario] = useState(null) // null | 'nueva' | campana
  const [porLanzar, setPorLanzar] = useState(null)
  const [ocupadas, setOcupadas] = useState(new Set())

  useEffect(() => {
    let vigente = true
    listarCampanas({ estado })
      .then(r => {
        if (!vigente) return
        setCampanas(r.datos)
        setCursor(r.pagina.tiene_mas ? r.pagina.siguiente_cursor : null)
        setError('')
      })
      .catch(err => vigente && setError(err.mensajeUsuario))
      .finally(() => vigente && setCargando(false))
    return () => { vigente = false }
  }, [estado])

  const recargar = async () => {
    try {
      const r = await listarCampanas({ estado })
      setCampanas(r.datos)
      setCursor(r.pagina.tiene_mas ? r.pagina.siguiente_cursor : null)
    } catch (err) {
      setError(err.mensajeUsuario)
    }
  }

  const verMas = async () => {
    setCargando(true)
    try {
      const r = await listarCampanas({ estado, cursor })
      setCampanas(lista => [...lista, ...r.datos])
      setCursor(r.pagina.tiene_mas ? r.pagina.siguiente_cursor : null)
    } catch (err) {
      setError(err.mensajeUsuario)
    } finally {
      setCargando(false)
    }
  }

  const actualizar = (id, cambios) => setCampanas(lista => lista.map(c => (c.id === id ? { ...c, ...cambios } : c)))
  const marcar = (id, ocupada) => setOcupadas(prev => {
    const n = new Set(prev)
    if (ocupada) n.add(id)
    else n.delete(id)
    return n
  })

  // Errores de la API llegan al modal de confirmacion, que los muestra.
  const lanzar = async campana => {
    marcar(campana.id, true)
    try {
      const r = await lanzarCampana(campana.id)
      setPorLanzar(null)
      actualizar(campana.id, { estado: 'en_curso' })
      sileo.success({ title: 'Campaña lanzada', description: `${r.total} mensajes, tiempo estimado ${duracion(r.duracion_estimada_segundos)}` })
    } finally {
      marcar(campana.id, false)
    }
  }

  const cancelar = campana => confirmar({
    titulo: `¿Cancelar el envío de "${campana.nombre}"?`,
    descripcion: 'Los mensajes pendientes no se enviarán y sus créditos se liberan.',
    etiqueta: 'Cancelar envío',
    alConfirmar: async () => {
      marcar(campana.id, true)
      try {
        const r = await cancelarCampana(campana.id)
        actualizar(campana.id, { estado: 'cancelada' })
        sileo.success({ title: 'Envío cancelado', description: `${r.envios_cancelados} mensajes cancelados, ${r.creditos_liberados} créditos liberados` })
      } catch (err) {
        sileo.error({ title: 'No se pudo cancelar', description: err.mensajeUsuario })
      } finally {
        marcar(campana.id, false)
      }
    },
  })

  const eliminar = campana => confirmar({
    titulo: `¿Eliminar "${campana.nombre}"?`,
    alConfirmar: async () => {
      try {
        await eliminarCampana(campana.id)
        setCampanas(lista => lista.filter(c => c.id !== campana.id))
        sileo.success({ title: 'Campaña eliminada' })
      } catch (err) {
        sileo.error({ title: 'No se pudo eliminar', description: err.mensajeUsuario })
      }
    },
  })

  const alGuardar = (guardada, { reabrir = false } = {}) => {
    setFormulario(reabrir ? guardada : null)
    recargar()
  }

  const alTerminar = useCallback(p => actualizar(p.campana_id, { estado: p.estado }), [])

  return (
    <div className="pagina" style={{ background: '#f8f9fa' }}>
      <div className="pagina-encabezado" style={{ alignItems: 'center' }}>
        <h1 className="pagina-titulo">Campañas</h1>
        <button className="boton boton-primario" style={{ padding: '9px 22px' }} onClick={() => setFormulario('nueva')}>+ Nueva campaña</button>
      </div>

      <div className="pestanas" role="tablist">
        {PESTANAS.map(p => (
          <button key={p.valor} role="tab" aria-selected={estado === p.valor} className={`pestana${estado === p.valor ? ' activa' : ''}`} onClick={() => setEstado(p.valor)}>
            {p.label}
          </button>
        ))}
      </div>

      <AlertBox>{error}</AlertBox>

      {cargando && campanas.length === 0 && <div style={{ textAlign: 'center', color: '#aaa', padding: 40 }}>Cargando campañas...</div>}
      {!cargando && campanas.length === 0 && !error && (
        <div style={{ textAlign: 'center', color: '#aaa', padding: 60 }}>
          <p>{estado ? 'No hay campañas en este estado.' : 'No hay campañas creadas.'}</p>
          {!estado && <p style={{ fontSize: '0.82rem', marginTop: 6 }}>Crea una nueva campaña para comenzar.</p>}
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {campanas.map(c => (
          <TarjetaCampana
            key={c.id}
            campana={c}
            ocupada={ocupadas.has(c.id)}
            onLanzar={setPorLanzar}
            onEditar={setFormulario}
            onEliminar={eliminar}
            onCancelar={cancelar}
            onTermino={alTerminar}
          />
        ))}
      </div>

      {cursor && (
        <div style={{ textAlign: 'center', marginTop: 16 }}>
          <button className="boton boton-secundario" disabled={cargando} onClick={verMas}>{cargando ? 'Cargando...' : 'Ver más'}</button>
        </div>
      )}

      {formulario && (
        <FormularioCampana
          key={formulario === 'nueva' ? 'nueva' : formulario.id}
          campana={formulario === 'nueva' ? null : formulario}
          onCerrar={() => setFormulario(null)}
          onGuardada={alGuardar}
        />
      )}
      {porLanzar && <ConfirmarLanzamiento campana={porLanzar} onCerrar={() => setPorLanzar(null)} onConfirmar={lanzar} />}
    </div>
  )
}
