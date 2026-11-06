import { useEffect, useState } from 'react'
import { sileo } from 'sileo'
import AlertBox from '../components/auth/AlertBox'
import Boton from '../components/ui/Boton'
import Insignia from '../components/ui/Insignia'
import Pagina, { Vacio } from '../components/ui/Pagina'
import { ContenedorTabla, Tabla } from '../components/ui/Tabla'
import { ESTADOS_CORREO, TIPOS_CORREO, pausarCola, reanudarCola, tareasCorreo } from '../api/notificaciones'
import { fechaHora } from '../api/envio'

const INTERVALO_MS = 4000

// Correos pendientes, enviados y fallidos. El contenido nunca se muestra. Solo staff.
export default function ColaCorreosPage() {
  const [tareas, setTareas] = useState([])
  const [pausada, setPausada] = useState(false)
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState('')
  const [cambiando, setCambiando] = useState(false)

  useEffect(() => {
    let vigente = true
    const cargar = () => tareasCorreo()
      .then(r => { if (vigente) { setTareas(r.datos); setPausada(r.pausada); setError('') } })
      .catch(err => vigente && setError(err.mensajeUsuario))
      .finally(() => vigente && setCargando(false))
    cargar()
    const t = setInterval(cargar, INTERVALO_MS)
    return () => { vigente = false; clearInterval(t) }
  }, [])

  const alternar = async () => {
    setCambiando(true)
    try {
      const r = pausada ? await reanudarCola() : await pausarCola()
      setPausada(r.pausada)
      sileo.success({ title: r.pausada ? 'Cola pausada' : 'Cola reanudada' })
    } catch (err) {
      sileo.error({ title: 'No se pudo cambiar la cola', description: err.mensajeUsuario })
    } finally {
      setCambiando(false)
    }
  }

  const cuenta = estado => tareas.filter(t => t.estado === estado).length

  return (
    <Pagina
      titulo="Cola de correos"
      subtitulo="Últimos 50 correos. Se actualiza cada 4 segundos."
      acciones={<>
        <Insignia color={pausada ? 'amarilla' : 'verde'} grande>{pausada ? 'Pausada' : 'Procesando'}</Insignia>
        <Boton variante={pausada ? 'primario' : 'secundario'} disabled={cambiando} onClick={alternar}>{pausada ? 'Reanudar' : 'Pausar'}</Boton>
      </>}
    >
      <div className="mb-4 flex flex-wrap gap-2">
        {Object.entries(ESTADOS_CORREO).map(([clave, e]) => (
          <Insignia key={clave} color={e.color}>{e.label}: {cuenta(clave)}</Insignia>
        ))}
      </div>
      <AlertBox>{error}</AlertBox>
      <ContenedorTabla>
        {cargando ? <Vacio>Cargando cola...</Vacio> : tareas.length === 0 ? <Vacio>No hay correos en la cola.</Vacio> : (
          <Tabla>
            <thead><tr><th>Tipo</th><th>Destinatario</th><th>Asunto</th><th>Estado</th><th>Intentos</th><th>Creado</th></tr></thead>
            <tbody>
              {tareas.map(t => {
                const estado = ESTADOS_CORREO[t.estado] || { label: t.estado, color: 'gris' }
                return (
                  <tr key={t.id}>
                    <td className="whitespace-nowrap">{TIPOS_CORREO[t.tipo] || t.tipo}</td>
                    <td>{t.destinatario}</td>
                    <td className="max-w-[260px] truncate text-gray-600">{t.asunto}</td>
                    <td>
                      <Insignia color={estado.color}>{estado.label}</Insignia>
                      {t.error && <div className="mt-1 max-w-[240px] text-[0.72rem] text-red-700">{t.error}</div>}
                    </td>
                    <td className="text-center">{t.intentos}</td>
                    <td className="whitespace-nowrap text-[0.78rem] text-gray-400">{fechaHora(t.creada_en)}</td>
                  </tr>
                )
              })}
            </tbody>
          </Tabla>
        )}
      </ContenedorTabla>
    </Pagina>
  )
}
