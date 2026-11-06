import { useCallback, useEffect, useState } from 'react'
import { sileo } from 'sileo'
import AlertBox from '../components/auth/AlertBox'
import Boton from '../components/ui/Boton'
import Pagina, { Vacio } from '../components/ui/Pagina'
import Pestanas from '../components/ui/Pestanas'
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
    <Pagina titulo="Campañas" acciones={<Boton className="px-[22px]" onClick={() => setFormulario('nueva')}>+ Nueva campaña</Boton>}>
      <Pestanas opciones={PESTANAS} valor={estado} onCambiar={setEstado} />

      <AlertBox>{error}</AlertBox>

      {cargando && campanas.length === 0 && <Vacio>Cargando campañas...</Vacio>}
      {!cargando && campanas.length === 0 && !error && (
        <Vacio>
          <p>{estado ? 'No hay campañas en este estado.' : 'No hay campañas creadas.'}</p>
          {!estado && <p className="mt-1.5 text-[0.82rem]">Crea una nueva campaña para comenzar.</p>}
        </Vacio>
      )}

      <div className="flex flex-col gap-3">
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
        <div className="mt-4 text-center">
          <Boton variante="secundario" disabled={cargando} onClick={verMas}>{cargando ? 'Cargando...' : 'Ver más'}</Boton>
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
    </Pagina>
  )
}
