import { useEffect, useState } from 'react'
import { sileo } from 'sileo'
import AlertBox from '../components/auth/AlertBox'
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
    <div className="pagina" style={{ background: '#f8f9fa' }}>
      <h1 className="pagina-titulo" style={{ marginBottom: 20 }}>Mensajes</h1>

      <div className="filtros">
        <input className="entrada" style={{ width: 260 }} placeholder="Buscar por texto o teléfono..." value={busqueda} onChange={e => setBusqueda(e.target.value)} />
        <select className="entrada" value={direccion} onChange={e => setDireccion(e.target.value)}>
          <option value="">Enviados y recibidos</option>
          <option value="saliente">Solo enviados</option>
          <option value="entrante">Solo recibidos</option>
        </select>
        <select className="entrada" value={estado} onChange={e => setEstado(e.target.value)}>
          <option value="">Todos los estados</option>
          {Object.entries(ESTADOS_ENTREGA).map(([valor, e]) => <option key={valor} value={valor}>{e.label}</option>)}
        </select>
      </div>

      {seleccion.size > 0 && (
        <div className="barra-seleccion">
          <strong>{plural(seleccion.size, 'mensaje seleccionado', 'mensajes seleccionados')}</strong>
          <button className="boton boton-peligro" style={{ padding: '6px 16px', fontSize: '0.82rem' }} onClick={eliminar}>Eliminar seleccionados</button>
          <button className="boton boton-secundario" style={{ padding: '6px 14px', fontSize: '0.8rem' }} onClick={() => setSeleccion(new Set())}>Cancelar selección</button>
        </div>
      )}

      <AlertBox>{error}</AlertBox>

      <div className="tabla-contenedor">
        {cargando && mensajes.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 40, color: '#aaa' }}>Cargando mensajes...</div>
        ) : mensajes.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 60, color: '#aaa' }}>
            {texto || direccion || estado ? 'Ningún mensaje coincide con los filtros.' : 'Aún no hay mensajes. Lanza una campaña para empezar.'}
          </div>
        ) : (
          <table style={{ opacity: cargando ? 0.6 : 1 }}>
            <thead>
              <tr>
                <th style={{ width: 36 }}><input type="checkbox" className="casilla" checked={todos} onChange={() => setSeleccion(todos ? new Set() : new Set(mensajes.map(m => m.id)))} aria-label="Seleccionar todos" /></th>
                <th>Contacto</th><th>Mensaje</th><th>Campaña</th><th>Estado</th><th>Fecha</th>
              </tr>
            </thead>
            <tbody>
              {mensajes.map(m => {
                const est = ESTADOS_ENTREGA[m.estado] || ESTADOS_ENTREGA.pendiente
                const entrante = m.direccion === 'entrante'
                return (
                  <tr key={m.id} className={seleccion.has(m.id) ? 'seleccionada' : ''}>
                    <td><input type="checkbox" className="casilla" checked={seleccion.has(m.id)} onChange={() => alternar(m.id)} /></td>
                    <td>
                      <div style={{ fontWeight: 600 }}>{m.nombre || mostrarTelefono(m.telefono)}</div>
                      {m.nombre && <div style={{ fontFamily: 'monospace', fontSize: '0.75rem', color: '#9ca3af' }}>{mostrarTelefono(m.telefono)}</div>}
                    </td>
                    <td style={{ maxWidth: 360 }}>
                      <span className={`direccion ${entrante ? 'entrante' : 'saliente'}`}>{entrante ? 'Recibido' : 'Enviado'}</span>
                      <span className="texto-recortado">{m.texto}</span>
                    </td>
                    <td style={{ color: '#6b7280' }}>{m.campana || <span style={{ color: '#d1d5db' }}>Chat</span>}</td>
                    <td>{entrante ? <span className="status-pill pill-read">Recibido</span> : <span className={`status-pill ${est.clase}`}>{est.label}</span>}</td>
                    <td style={{ whiteSpace: 'nowrap', color: '#9ca3af', fontSize: '0.78rem' }}>{fechaHora(m.fecha)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>

      {(pagina > 1 || siguiente) && (
        <div className="paginacion">
          <button className="boton boton-secundario" style={{ padding: '6px 14px' }} disabled={pagina === 1 || cargando} onClick={() => ir(cursores.slice(0, -1))}>Anterior</button>
          <span>Página {pagina}</span>
          <button className="boton boton-secundario" style={{ padding: '6px 14px' }} disabled={!siguiente || cargando} onClick={() => ir([...cursores, siguiente])}>Siguiente</button>
        </div>
      )}
    </div>
  )
}
