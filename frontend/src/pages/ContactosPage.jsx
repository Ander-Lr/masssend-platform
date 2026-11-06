import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { sileo } from 'sileo'
import AlertBox from '../components/auth/AlertBox'
import FormField from '../components/auth/FormField'
import Modal from '../components/ui/Modal'
import Etiquetas from '../components/ui/Etiquetas'
import Boton, { BotonMini } from '../components/ui/Boton'
import Insignia from '../components/ui/Insignia'
import Pagina, { Vacio } from '../components/ui/Pagina'
import { BarraSeleccion, ContenedorTabla, Paginacion, Tabla } from '../components/ui/Tabla'
import { Ayuda, Etiqueta, claseCasilla, claseFiltro } from '../components/ui/Campo'
import { claseBoton } from '../components/ui/clases'
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
          <div className="mb-4">
            <Etiqueta>Teléfono</Etiqueta>
            <div className="flex overflow-hidden rounded-lg border-[1.5px] border-gray-200 focus-within:border-marca">
              <select value={pais} onChange={e => setPais(e.target.value)} aria-label="País"
                className="border-r border-gray-200 bg-gray-50 px-2.5 text-[0.88rem] font-semibold text-gray-700 outline-none">
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
                className="min-w-0 flex-1 px-3 py-2.5 text-[0.9rem] outline-none"
              />
            </div>
            {vistaPrevia && !vistaPrevia.ok && (
              <Ayuda color="text-amber-700">{vistaPrevia.error}</Ayuda>
            )}
          </div>
        )}
        <FormField label="Nombre (opcional)" value={nombre} onChange={setNombre} required={false} placeholder="Nombre completo" autoFocus={editando} />
        <FormField label="Etiquetas (opcional, separadas por coma)" value={etiquetas} onChange={setEtiquetas} required={false} placeholder="cliente, lead" />
        {editando && <FormField label="Notas (opcional)" value={notas} onChange={setNotas} required={false} />}
        <AlertBox>{error}</AlertBox>
        <div className="flex justify-end gap-2.5">
          <Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton>
          <Boton type="submit" disabled={guardando}>{guardando ? 'Guardando...' : 'Guardar'}</Boton>
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
    <Pagina
      titulo="Contactos"
      acciones={<>
        <Link to="/importar" className={claseBoton({ variante: 'indigo', extra: 'px-[18px] py-2 text-[0.85rem] font-semibold' })}>Importar CSV</Link>
        <Boton className="px-[18px] py-2 text-[0.85rem]" onClick={() => setFormulario('nuevo')}>+ Agregar contacto</Boton>
      </>}
    >
      <div className="mb-[18px] flex flex-wrap gap-2.5">
        <input className={`${claseFiltro} w-[260px]`} placeholder="Buscar por nombre o teléfono..." value={busqueda} onChange={e => setBusqueda(e.target.value)} />
        <select className={claseFiltro} value={etiqueta} onChange={e => setEtiqueta(e.target.value)}>
          <option value="">Todas las etiquetas</option>
          {disponibles.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
      </div>

      {seleccion.size > 0 && (
        <BarraSeleccion texto={plural(seleccion.size, 'contacto seleccionado', 'contactos seleccionados')}>
          <Boton variante="peligro" tamano="sm" onClick={eliminarSeleccion}>Eliminar seleccionados</Boton>
          <Boton variante="secundario" tamano="sm" onClick={() => setSeleccion(new Set())}>Cancelar selección</Boton>
        </BarraSeleccion>
      )}

      <AlertBox>{error}</AlertBox>

      <ContenedorTabla>
        {cargando && contactos.length === 0 ? (
          <Vacio>Cargando contactos...</Vacio>
        ) : contactos.length === 0 ? (
          <Vacio>
            {texto || etiqueta ? 'Ningún contacto coincide con la búsqueda.' : 'Aún no tienes contactos. Agrega uno o importa un CSV.'}
          </Vacio>
        ) : (
          <Tabla atenuada={cargando}>
            <thead>
              <tr>
                <th className="w-9"><input type="checkbox" className={claseCasilla} checked={todosMarcados} onChange={alternarTodos} aria-label="Seleccionar todos" /></th>
                <th>Nombre</th><th>Teléfono</th><th>Etiquetas</th><th>Estado</th><th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {contactos.map(c => (
                <tr key={c.id} className={seleccion.has(c.id) ? 'bg-indigo-50' : ''}>
                  <td><input type="checkbox" className={claseCasilla} checked={seleccion.has(c.id)} onChange={() => alternar(c.id)} aria-label={`Seleccionar ${c.nombre || c.telefono}`} /></td>
                  <td className="font-semibold">{c.nombre || <span className="font-normal text-gray-300">Sin nombre</span>}</td>
                  <td className="font-mono text-gray-600">{mostrarTelefono(c.telefono)}</td>
                  <td><Etiquetas lista={c.etiquetas} /></td>
                  <td>
                    <Insignia color={c.dado_de_baja ? 'roja' : 'verde'}>{c.dado_de_baja ? 'Baja' : 'Activo'}</Insignia>
                  </td>
                  <td>
                    <div className="flex gap-1.5">
                      <BotonMini onClick={() => setFormulario(c)}>Editar</BotonMini>
                      <BotonMini color={c.dado_de_baja ? 'verde' : 'amarillo'} onClick={() => alternarBaja(c)}>
                        {c.dado_de_baja ? 'Activar' : 'Dar de baja'}
                      </BotonMini>
                      <BotonMini color="rojo" onClick={() => eliminar(c)}>Eliminar</BotonMini>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </Tabla>
        )}
      </ContenedorTabla>

      {(pagina > 1 || siguiente) && (
        <Paginacion pagina={pagina} hayAnterior={pagina > 1} haySiguiente={Boolean(siguiente)} cargando={cargando} onAnterior={irAnterior} onSiguiente={irSiguiente} />
      )}

      {formulario && (
        <FormularioContacto
          contacto={formulario === 'nuevo' ? null : formulario}
          onCerrar={() => setFormulario(null)}
          onGuardado={alGuardar}
        />
      )}
    </Pagina>
  )
}
