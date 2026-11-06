import { useEffect, useState } from 'react'
import { sileo } from 'sileo'
import AlertBox from '../components/auth/AlertBox'
import Boton from '../components/ui/Boton'
import Insignia from '../components/ui/Insignia'
import Pagina, { Vacio } from '../components/ui/Pagina'
import { BarraSeleccion, ContenedorTabla, Paginacion, Tabla } from '../components/ui/Tabla'
import { claseCasilla, claseFiltro } from '../components/ui/Campo'
import { confirmar } from '../components/ui/confirmar'
import { ESTADOS_ENTREGA, eliminarMensajes, fechaHora, listarMensajes } from '../api/envio'
import { mostrarTelefono } from '../utils/telefono'

const plural = (n, uno, varios) => `${n} ${n === 1 ? uno : varios}`

function useDiferido(valor, ms = 350) {
  const [diferido, setDiferido] = useState(valor)
  useEffect(() => {
    const t = setTimeout(() => setDiferido(valor), ms)
    return () => clearTimeout(t)
  }, [valor, ms])
  return diferido
}

// Historial de los mensajes de la cuenta: los de campañas, el chat y las respuestas recibidas.
export default function MensajesPage() {
  const [mensajes, setMensajes] = useState([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState('')
  const [busqueda, setBusqueda] = useState('')
  const [direccion, setDireccion] = useState('')
  const [estado, setEstado] = useState('')
  const [cursores, setCursores] = useState([null])
  const [siguiente, setSiguiente] = useState(null)
  const [seleccion, setSeleccion] = useState(new Set())
  const texto = useDiferido(busqueda.trim())
  const pagina = cursores.length

  const pedir = cursor => listarMensajes({ texto, direccion, estado, cursor })
  const mostrar = r => {
    setMensajes(r.datos)
    setSiguiente(r.pagina.tiene_mas ? r.pagina.siguiente_cursor : null)
    setSeleccion(new Set())
    setError('')
  }

  useEffect(() => {
    let vigente = true
    listarMensajes({ texto, direccion, estado })
      .then(r => {
        if (!vigente) return
        setMensajes(r.datos)
        setSiguiente(r.pagina.tiene_mas ? r.pagina.siguiente_cursor : null)
        setCursores([null])
        setSeleccion(new Set())
        setError('')
      })
      .catch(err => vigente && setError(err.mensajeUsuario))
      .finally(() => vigente && setCargando(false))
    return () => { vigente = false }
  }, [texto, direccion, estado])

  const ir = async nuevos => {
    setCargando(true)
    try {
      mostrar(await pedir(nuevos[nuevos.length - 1]))
      setCursores(nuevos)
    } catch (err) {
      setError(err.mensajeUsuario)
    } finally {
      setCargando(false)
    }
  }

  const alternar = id => setSeleccion(prev => {
    const n = new Set(prev)
    if (n.has(id)) n.delete(id)
    else n.add(id)
    return n
  })
  const todos = mensajes.length > 0 && mensajes.every(m => seleccion.has(m.id))

  const eliminar = () => confirmar({
    titulo: `¿Eliminar ${plural(seleccion.size, 'mensaje', 'mensajes')} del historial?`,
    descripcion: 'Solo se borran del historial de MassSend, no del WhatsApp del contacto.',
    alConfirmar: async () => {
      try {
        const r = await eliminarMensajes([...seleccion])
        sileo.success({ title: plural(r.eliminados, 'mensaje eliminado', 'mensajes eliminados') })
        ir(cursores)
      } catch (err) {
        sileo.error({ title: 'No se pudo eliminar', description: err.mensajeUsuario })
      }
    },
  })

  return (
    <Pagina titulo="Mensajes">
      <div className="mb-[18px] flex flex-wrap gap-2.5">
        <input className={`${claseFiltro} w-[260px]`} placeholder="Buscar por texto o teléfono..." value={busqueda} onChange={e => setBusqueda(e.target.value)} />
        <select className={claseFiltro} value={direccion} onChange={e => setDireccion(e.target.value)}>
          <option value="">Enviados y recibidos</option>
          <option value="saliente">Solo enviados</option>
          <option value="entrante">Solo recibidos</option>
        </select>
        <select className={claseFiltro} value={estado} onChange={e => setEstado(e.target.value)}>
          <option value="">Todos los estados</option>
          {Object.entries(ESTADOS_ENTREGA).map(([valor, e]) => <option key={valor} value={valor}>{e.label}</option>)}
        </select>
      </div>

      {seleccion.size > 0 && (
        <BarraSeleccion texto={plural(seleccion.size, 'mensaje seleccionado', 'mensajes seleccionados')}>
          <Boton variante="peligro" tamano="sm" onClick={eliminar}>Eliminar seleccionados</Boton>
          <Boton variante="secundario" tamano="sm" onClick={() => setSeleccion(new Set())}>Cancelar selección</Boton>
        </BarraSeleccion>
      )}

      <AlertBox>{error}</AlertBox>

      <ContenedorTabla>
        {cargando && mensajes.length === 0 ? (
          <Vacio>Cargando mensajes...</Vacio>
        ) : mensajes.length === 0 ? (
          <Vacio>{texto || direccion || estado ? 'Ningún mensaje coincide con los filtros.' : 'Aún no hay mensajes. Lanza una campaña para empezar.'}</Vacio>
        ) : (
          <Tabla atenuada={cargando}>
            <thead>
              <tr>
                <th className="w-9"><input type="checkbox" className={claseCasilla} checked={todos} onChange={() => setSeleccion(todos ? new Set() : new Set(mensajes.map(m => m.id)))} aria-label="Seleccionar todos" /></th>
                <th>Contacto</th><th>Mensaje</th><th>Campaña</th><th>Estado</th><th>Fecha</th>
              </tr>
            </thead>
            <tbody>
              {mensajes.map(m => {
                const est = ESTADOS_ENTREGA[m.estado] || ESTADOS_ENTREGA.pendiente
                const entrante = m.direccion === 'entrante'
                return (
                  <tr key={m.id} className={seleccion.has(m.id) ? 'bg-indigo-50' : ''}>
                    <td><input type="checkbox" className={claseCasilla} checked={seleccion.has(m.id)} onChange={() => alternar(m.id)} /></td>
                    <td>
                      <div className="font-semibold">{m.nombre || mostrarTelefono(m.telefono)}</div>
                      {m.nombre && <div className="font-mono text-[0.75rem] text-gray-400">{mostrarTelefono(m.telefono)}</div>}
                    </td>
                    <td className="max-w-[360px]">
                      <span className={`mr-1.5 inline-block rounded px-1.5 py-px text-[0.68rem] font-bold ${entrante ? 'bg-emerald-50 text-emerald-700' : 'bg-indigo-50 text-indigo-700'}`}>
                        {entrante ? 'Recibido' : 'Enviado'}
                      </span>
                      <span className="text-gray-700">{m.texto}</span>
                    </td>
                    <td className="text-gray-500">{m.campana || <span className="text-gray-300">Chat</span>}</td>
                    <td>{entrante ? <Insignia color="verde">Recibido</Insignia> : <Insignia color={est.color}>{est.label}</Insignia>}</td>
                    <td className="whitespace-nowrap text-[0.78rem] text-gray-400">{fechaHora(m.fecha)}</td>
                  </tr>
                )
              })}
            </tbody>
          </Tabla>
        )}
      </ContenedorTabla>

      {(pagina > 1 || siguiente) && (
        <Paginacion
          pagina={pagina} hayAnterior={pagina > 1} haySiguiente={Boolean(siguiente)} cargando={cargando}
          onAnterior={() => ir(cursores.slice(0, -1))} onSiguiente={() => ir([...cursores, siguiente])}
        />
      )}
    </Pagina>
  )
}
