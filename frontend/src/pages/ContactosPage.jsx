import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { sileo } from 'sileo'
import AlertBox from '../components/auth/AlertBox'
import FormField from '../components/auth/FormField'
import Modal from '../components/ui/Modal'
import Etiquetas from '../components/ui/Etiquetas'
import { confirmar } from '../components/ui/confirmar'
import {
  crearContacto, editarContacto, eliminarContacto, eliminarContactos, etiquetas as pedirEtiquetas, listarContactos,
} from '../api/contactos'
import { mostrarTelefono, revisarTelefono } from '../utils/telefono'

const plural = (n, uno, varios) => `${n} ${n === 1 ? uno : varios}`

// Retrasa la busqueda mientras el usuario escribe.
function useDiferido(valor, ms = 350) {
  const [diferido, setDiferido] = useState(valor)
  useEffect(() => {
    const t = setTimeout(() => setDiferido(valor), ms)
    return () => clearTimeout(t)
  }, [valor, ms])
  return diferido
}

function FormularioContacto({ contacto, onCerrar, onGuardado }) {
  const editando = Boolean(contacto)
  const [pais, setPais] = useState('ec')
  const [telefono, setTelefono] = useState('')
  const [nombre, setNombre] = useState(contacto?.nombre || '')
  const [etiquetas, setEtiquetas] = useState(contacto?.etiquetas.join(', ') || '')
  const [notas, setNotas] = useState(contacto?.datos?.notas || '')
  const [error, setError] = useState('')
  const [guardando, setGuardando] = useState(false)

  // En Ecuador se acepta 0991234567, 991234567 o el numero ya con 593.
  const soloDigitos = telefono.replace(/\D/g, '')
  const numeroCompleto = pais !== 'ec' || soloDigitos.startsWith('593') ? telefono : `593${soloDigitos.replace(/^0/, '')}`
  const vistaPrevia = !editando && telefono ? revisarTelefono(numeroCompleto) : null

  const guardar = async e => {
    e.preventDefault()
    setError('')
    setGuardando(true)
    try {
      if (editando) {
        await editarContacto(contacto.id, { nombre, etiquetas, datos: { notas } })
        sileo.success({ title: 'Contacto actualizado', description: nombre || mostrarTelefono(contacto.telefono) })
      } else {
        const creado = await crearContacto({ telefono: numeroCompleto, nombre, etiquetas })
        sileo.success({ title: 'Contacto guardado', description: creado.nombre || mostrarTelefono(creado.telefono) })
      }
      onGuardado()
    } catch (err) {
      setError(err.mensajeUsuario)
      setGuardando(false)
    }
  }

  return (
    <Modal
      titulo={editando ? 'Editar contacto' : 'Agregar contacto'}
      subtitulo={editando ? mostrarTelefono(contacto.telefono) : 'Si el teléfono ya existe, se actualizan sus datos.'}
      onCerrar={onCerrar}
    >
      <form onSubmit={guardar}>
        {!editando && (
          <div className="campo">
            <label>Teléfono</label>
            <div className="telefono-grupo">
              <select value={pais} onChange={e => setPais(e.target.value)} aria-label="País">
                <option value="ec">EC +593</option>
                <option value="otro">Otro país</option>
              </select>
              <input
                value={telefono}
                onChange={e => setTelefono(e.target.value.replace(/[^\d+]/g, ''))}
                placeholder={pais === 'ec' ? '0991234567' : '573001234567 (con código de país)'}
                maxLength={16}
                inputMode="tel"
                required
                autoFocus
              />
            </div>
            {vistaPrevia && !vistaPrevia.ok && (
              <p style={{ color: '#b45309', fontSize: '0.76rem', marginTop: 6 }}>{vistaPrevia.error}</p>
            )}
          </div>
        )}
        <FormField label="Nombre (opcional)" value={nombre} onChange={setNombre} required={false} placeholder="Nombre completo" autoFocus={editando} />
        <FormField label="Etiquetas (opcional, separadas por coma)" value={etiquetas} onChange={setEtiquetas} required={false} placeholder="cliente, lead" />
        {editando && <FormField label="Notas (opcional)" value={notas} onChange={setNotas} required={false} />}
        <AlertBox>{error}</AlertBox>
        <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
          <button type="button" className="boton boton-secundario" onClick={onCerrar}>Cancelar</button>
          <button type="submit" className="boton boton-primario" disabled={guardando}>{guardando ? 'Guardando...' : 'Guardar'}</button>
        </div>
      </form>
    </Modal>
  )
}

export default function ContactosPage() {
  const [contactos, setContactos] = useState([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState('')
  const [busqueda, setBusqueda] = useState('')
  const [etiqueta, setEtiqueta] = useState('')
  const [disponibles, setDisponibles] = useState([])
  // Paginacion por cursor: se guarda el cursor de cada pagina visitada.
  const [cursores, setCursores] = useState([null])
  const [siguiente, setSiguiente] = useState(null)
  const [seleccion, setSeleccion] = useState(new Set())
  const [formulario, setFormulario] = useState(null) // null | 'nuevo' | contacto
  const texto = useDiferido(busqueda.trim())
  const pagina = cursores.length

  const cargar = useCallback(async cursor => {
    setCargando(true)
    try {
      const r = await listarContactos({ texto, etiqueta, cursor })
      setContactos(r.datos)
      setSiguiente(r.pagina.tiene_mas ? r.pagina.siguiente_cursor : null)
      setError('')
    } catch (err) {
      setError(err.mensajeUsuario)
    } finally {
      setCargando(false)
      setSeleccion(new Set())
    }
  }, [texto, etiqueta])

  const refrescarEtiquetas = useCallback(() => {
    pedirEtiquetas().then(r => setDisponibles(r.datos)).catch(() => {})
  }, [])

  useEffect(() => {
    let vigente = true
    listarContactos({ texto, etiqueta })
      .then(r => {
        if (!vigente) return
        setContactos(r.datos)
        setSiguiente(r.pagina.tiene_mas ? r.pagina.siguiente_cursor : null)
        setCursores([null])
        setSeleccion(new Set())
        setError('')
      })
      .catch(err => vigente && setError(err.mensajeUsuario))
      .finally(() => vigente && setCargando(false))
    return () => { vigente = false }
  }, [texto, etiqueta])

  useEffect(refrescarEtiquetas, [refrescarEtiquetas])

  const recargar = () => cargar(cursores[cursores.length - 1])
  const irSiguiente = () => { setCursores(c => [...c, siguiente]); cargar(siguiente) }
  const irAnterior = () => {
    const nuevos = cursores.slice(0, -1)
    setCursores(nuevos)
    cargar(nuevos[nuevos.length - 1])
  }

  const alternar = id => setSeleccion(prev => {
    const n = new Set(prev)
    if (n.has(id)) n.delete(id)
    else n.add(id)
    return n
  })
  const todosMarcados = contactos.length > 0 && contactos.every(c => seleccion.has(c.id))
  const alternarTodos = () => setSeleccion(todosMarcados ? new Set() : new Set(contactos.map(c => c.id)))

  const eliminarSeleccion = () => confirmar({
    titulo: `¿Eliminar ${plural(seleccion.size, 'contacto', 'contactos')}?`,
    alConfirmar: async () => {
      try {
        const r = await eliminarContactos([...seleccion])
        sileo.success({ title: `${plural(r.eliminados, 'contacto eliminado', 'contactos eliminados')}` })
        recargar()
        refrescarEtiquetas()
      } catch (err) {
        sileo.error({ title: 'No se pudo eliminar', description: err.mensajeUsuario })
      }
    },
  })

  const eliminar = c => confirmar({
    titulo: `¿Eliminar a ${c.nombre || mostrarTelefono(c.telefono)}?`,
    alConfirmar: async () => {
      try {
        await eliminarContacto(c.id)
        sileo.success({ title: 'Contacto eliminado' })
        recargar()
      } catch (err) {
        sileo.error({ title: 'No se pudo eliminar', description: err.mensajeUsuario })
      }
    },
  })

  // Un contacto dado de baja no recibe mensajes de campañas.
  const alternarBaja = async c => {
    try {
      await editarContacto(c.id, { dado_de_baja: !c.dado_de_baja })
      sileo.success({ title: c.dado_de_baja ? 'Contacto activado' : 'Contacto dado de baja', description: c.nombre || mostrarTelefono(c.telefono) })
      setContactos(lista => lista.map(x => (x.id === c.id ? { ...x, dado_de_baja: !c.dado_de_baja } : x)))
    } catch (err) {
      sileo.error({ title: 'No se pudo actualizar', description: err.mensajeUsuario })
    }
  }

  const alGuardar = () => {
    setFormulario(null)
    recargar()
    refrescarEtiquetas()
  }

  return (
    <div className="pagina" style={{ background: '#f8f9fa' }}>
      <div className="pagina-encabezado" style={{ alignItems: 'center' }}>
        <h1 className="pagina-titulo">Contactos</h1>
        <div style={{ display: 'flex', gap: 10 }}>
          <Link to="/importar" className="boton boton-violeta" style={{ textDecoration: 'none', padding: '8px 18px', fontWeight: 600, fontSize: '0.85rem' }}>
            Importar CSV
          </Link>
          <button className="boton boton-primario" style={{ padding: '8px 18px', fontSize: '0.85rem' }} onClick={() => setFormulario('nuevo')}>
            + Agregar contacto
          </button>
        </div>
      </div>

      <div className="filtros">
        <input className="entrada" style={{ width: 260 }} placeholder="Buscar por nombre o teléfono..." value={busqueda} onChange={e => setBusqueda(e.target.value)} />
        <select className="entrada" value={etiqueta} onChange={e => setEtiqueta(e.target.value)}>
          <option value="">Todas las etiquetas</option>
          {disponibles.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
      </div>

      {seleccion.size > 0 && (
        <div className="barra-seleccion">
          <strong>{plural(seleccion.size, 'contacto seleccionado', 'contactos seleccionados')}</strong>
          <button className="boton boton-peligro" style={{ padding: '6px 16px', fontSize: '0.82rem' }} onClick={eliminarSeleccion}>Eliminar seleccionados</button>
          <button className="boton boton-secundario" style={{ padding: '6px 14px', fontSize: '0.8rem' }} onClick={() => setSeleccion(new Set())}>Cancelar selección</button>
        </div>
      )}

      <AlertBox>{error}</AlertBox>

      <div className="tabla-contenedor">
        {cargando && contactos.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 40, color: '#aaa' }}>Cargando contactos...</div>
        ) : contactos.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 60, color: '#aaa' }}>
            {texto || etiqueta ? 'Ningún contacto coincide con la búsqueda.' : 'Aún no tienes contactos. Agrega uno o importa un CSV.'}
          </div>
        ) : (
          <table style={{ opacity: cargando ? 0.6 : 1 }}>
            <thead>
              <tr>
                <th style={{ width: 36 }}><input type="checkbox" className="casilla" checked={todosMarcados} onChange={alternarTodos} aria-label="Seleccionar todos" /></th>
                <th>Nombre</th><th>Teléfono</th><th>Etiquetas</th><th>Estado</th><th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {contactos.map(c => (
                <tr key={c.id} className={seleccion.has(c.id) ? 'seleccionada' : ''}>
                  <td><input type="checkbox" className="casilla" checked={seleccion.has(c.id)} onChange={() => alternar(c.id)} aria-label={`Seleccionar ${c.nombre || c.telefono}`} /></td>
                  <td style={{ fontWeight: 600 }}>{c.nombre || <span style={{ color: '#d1d5db' }}>Sin nombre</span>}</td>
                  <td style={{ fontFamily: 'monospace', color: '#555' }}>{mostrarTelefono(c.telefono)}</td>
                  <td><Etiquetas lista={c.etiquetas} /></td>
                  <td>
                    <span className={`insignia ${c.dado_de_baja ? 'insignia-roja' : 'insignia-verde'}`}>{c.dado_de_baja ? 'Baja' : 'Activo'}</span>
                  </td>
                  <td>
                    <div style={{ display: 'flex', gap: 6 }}>
                      <button className="boton-mini gris" onClick={() => setFormulario(c)}>Editar</button>
                      <button className={`boton-mini ${c.dado_de_baja ? 'verde' : 'amarillo'}`} onClick={() => alternarBaja(c)}>
                        {c.dado_de_baja ? 'Activar' : 'Dar de baja'}
                      </button>
                      <button className="boton-mini rojo" onClick={() => eliminar(c)}>Eliminar</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {(pagina > 1 || siguiente) && (
        <div className="paginacion">
          <button className="boton boton-secundario" style={{ padding: '6px 14px' }} disabled={pagina === 1 || cargando} onClick={irAnterior}>Anterior</button>
          <span>Página {pagina}</span>
          <button className="boton boton-secundario" style={{ padding: '6px 14px' }} disabled={!siguiente || cargando} onClick={irSiguiente}>Siguiente</button>
        </div>
      )}

      {formulario && (
        <FormularioContacto
          contacto={formulario === 'nuevo' ? null : formulario}
          onCerrar={() => setFormulario(null)}
          onGuardado={alGuardar}
        />
      )}
    </div>
  )
}
