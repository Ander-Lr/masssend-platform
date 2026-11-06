import { useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { sileo } from 'sileo'
import AlertBox from '../components/auth/AlertBox'
import Boton from '../components/ui/Boton'
import Pagina from '../components/ui/Pagina'
import Tarjeta from '../components/ui/Tarjeta'
import { Cerrar, Fondo } from '../components/ui/Modal'
import { ContenedorTabla, Tabla } from '../components/ui/Tabla'
import { Etiqueta, claseCasilla, claseEntrada } from '../components/ui/Campo'
import { claseBoton } from '../components/ui/clases'
import { importarCsv } from '../api/contactos'
import {
  CAMPOS, SEPARADORES, asignacionPosicional, asignarColumnas, construirCsv, descargarPlantilla, leerCsv,
} from '../utils/csv'
import { mostrarTelefono, revisarTelefono } from '../utils/telefono'

const MAXIMO_MB = 5
const FILAS_VISIBLES = 200

function ZonaArchivo({ archivo, onArchivo }) {
  const entrada = useRef(null)
  const [arrastrando, setArrastrando] = useState(false)
  return (
    <div
      className={`mb-5 cursor-pointer rounded-xl border-2 border-dashed px-5 py-8 text-center transition-all hover:border-violet-600 hover:bg-violet-50 ${arrastrando ? 'border-violet-600 bg-violet-50' : 'border-violet-300 bg-purple-50/60'}`}
      onDragOver={e => { e.preventDefault(); setArrastrando(true) }}
      onDragLeave={() => setArrastrando(false)}
      onDrop={e => { e.preventDefault(); setArrastrando(false); onArchivo(e.dataTransfer.files[0]) }}
      onClick={() => entrada.current?.click()}
      role="button"
      tabIndex={0}
      onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') entrada.current?.click() }}
    >
      <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#7c3aed" strokeWidth="1.5" strokeLinecap="round" aria-hidden="true" className="mx-auto block">
        <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" />
      </svg>
      <p className="mt-2.5 mb-1 font-semibold text-violet-600">
        {archivo ? archivo.name : 'Arrastra tu CSV aquí o haz clic para seleccionar'}
      </p>
      <p className="text-[0.75rem] text-gray-400">Formatos .csv o .txt, máximo {MAXIMO_MB} MB</p>
      <input
        ref={entrada}
        type="file"
        accept=".csv,.txt"
        className="hidden"
        onChange={e => { onArchivo(e.target.files[0]); e.target.value = '' }}
      />
    </div>
  )
}

function Resultado({ resultado, onOtro }) {
  return (
    <div className="mb-6 rounded-xl border border-emerald-300 bg-emerald-100 px-6 py-5">
      <p className="mb-2 font-bold text-emerald-800">Importación completada</p>
      <div className="flex flex-wrap gap-6 text-[0.88rem]">
        <span>Total: <strong>{resultado.total}</strong></span>
        <span className="text-emerald-500">Creados: <strong>{resultado.creados}</strong></span>
        <span className="text-blue-500">Actualizados: <strong>{resultado.actualizados}</strong></span>
        <span className="text-red-500">Rechazados: <strong>{resultado.total_rechazadas}</strong></span>
      </div>
      {resultado.rechazadas.length > 0 && (
        <ContenedorTabla className="mt-3.5 max-h-60 overflow-y-auto">
          <Tabla>
            <thead><tr><th>Fila del archivo</th><th>Teléfono</th><th>Motivo</th></tr></thead>
            <tbody>
              {resultado.rechazadas.map((r, i) => (
                <tr key={i}><td>{r.fila}</td><td className="font-mono">{r.telefono || 'vacío'}</td><td className="text-red-800">{r.mensaje}</td></tr>
              ))}
            </tbody>
          </Tabla>
        </ContenedorTabla>
      )}
      {resultado.total_rechazadas > resultado.rechazadas.length && (
        <p className="mt-2 text-[0.78rem] text-gray-500">
          Se muestran las primeras {resultado.rechazadas.length} filas rechazadas.
        </p>
      )}
      <div className="mt-3.5 flex gap-2.5">
        <Boton variante="oscuro" className="px-5 py-2" onClick={onOtro}>Importar otro archivo</Boton>
        <Link to="/contactos" className={claseBoton({ variante: 'secundario', extra: 'px-5 py-2' })}>Ver contactos</Link>
      </div>
    </div>
  )
}

function VistaPrevia({ archivo, lectura, onCerrar, onImportado }) {
  const { encabezados, filas, conEncabezado } = lectura
  const [asignadas, setAsignadas] = useState(() => (conEncabezado ? asignarColumnas(encabezados) : asignacionPosicional(encabezados.length)))
  const [excluidas, setExcluidas] = useState(new Set())
  const [importando, setImportando] = useState(false)
  const [error, setError] = useState('')
  const columnaTelefono = Object.keys(asignadas).find(i => asignadas[i] === 'telefono')

  // Cada fila con sus campos asignados y la vista previa de su telefono.
  const vistas = useMemo(() => filas.map((celdas, i) => {
    const valor = campo => {
      const indice = Object.keys(asignadas).find(k => asignadas[k] === campo)
      return indice !== undefined ? celdas[indice] || '' : ''
    }
    const revision = columnaTelefono !== undefined ? revisarTelefono(valor('telefono')) : { ok: false, error: 'Sin columna de teléfono' }
    return {
      indice: i,
      fila: i + (conEncabezado ? 2 : 1),
      telefono: valor('telefono'),
      nombre: valor('nombre'),
      etiquetas: valor('etiquetas'),
      notas: valor('notas'),
      revision,
    }
  }), [filas, asignadas, columnaTelefono, conEncabezado])

  const validas = vistas.filter(v => v.revision.ok)
  const invalidas = vistas.length - validas.length
  const elegidas = validas.filter(v => !excluidas.has(v.indice))
  const todas = validas.length > 0 && excluidas.size === 0

  const alternar = indice => setExcluidas(prev => {
    const n = new Set(prev)
    if (n.has(indice)) n.delete(indice)
    else n.add(indice)
    return n
  })

  const importar = async () => {
    setError('')
    setImportando(true)
    try {
      const resultado = await importarCsv(new File([construirCsv(elegidas)], archivo.name.replace(/\.\w+$/, '.csv')))
      // El backend numera las filas del CSV enviado: se traducen a las del archivo original.
      resultado.rechazadas = resultado.rechazadas.map(r => ({ ...r, fila: elegidas[r.fila - 2]?.fila ?? r.fila }))
      sileo.success({ title: 'Importación completada', description: `${resultado.creados} nuevos, ${resultado.actualizados} actualizados, ${resultado.total_rechazadas} rechazados` })
      onImportado(resultado)
    } catch (err) {
      setError(err.mensajeUsuario)
      setImportando(false)
    }
  }

  return (
    <Fondo>
      <div role="dialog" aria-modal="true" aria-label="Vista previa del archivo" className="flex max-h-[90vh] w-full max-w-[920px] flex-col rounded-2xl bg-white shadow-2xl">
        <div className="border-b border-gray-200 px-6 pt-5 pb-4">
          <div className="flex justify-between gap-3">
            <div>
              <h2 className="text-[1.05rem] font-bold">Vista previa del archivo</h2>
              <p className="mt-1 text-[0.78rem] text-gray-500">{archivo.name} · {filas.length} filas encontradas</p>
            </div>
            <Cerrar onClick={onCerrar} />
          </div>
          {columnaTelefono === undefined && (
            <div className="mt-3 rounded-lg bg-amber-100 px-3.5 py-2 text-[0.78rem] text-amber-800">
              Asigna la columna <strong>Teléfono</strong> para poder importar.
            </div>
          )}
          <p className="mt-3 mb-2 text-[0.72rem] font-bold uppercase tracking-wide text-violet-600">Asigna cada columna del CSV a un campo</p>
          <div className="flex flex-wrap gap-2.5">
            {encabezados.map((encabezado, i) => (
              <div key={i} className="min-w-[140px]">
                <div className="mb-0.5 font-mono text-[0.7rem] text-gray-400">{encabezado}</div>
                <select
                  className={`w-full rounded-md border-[1.5px] px-2 py-1.5 text-[0.78rem] outline-none ${asignadas[i] === 'telefono' ? 'border-violet-600 bg-purple-50' : asignadas[i] ? 'border-violet-300 bg-white' : 'border-gray-200 bg-white'}`}
                  value={asignadas[i] || ''}
                  onChange={e => {
                    const campo = e.target.value
                    // Un campo solo puede venir de una columna.
                    setAsignadas(prev => Object.fromEntries(Object.entries(prev).map(([k, v]) => [k, Number(k) === i ? campo : v === campo && campo ? '' : v])))
                    setExcluidas(new Set())
                  }}
                >
                  {CAMPOS.map(c => <option key={c.valor} value={c.valor}>{c.label}</option>)}
                </select>
              </div>
            ))}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-6">
          <div className="sticky top-0 z-10 flex flex-wrap items-center gap-3 border-b border-gray-100 bg-white py-3 text-[0.82rem] text-gray-700">
            <label className="flex cursor-pointer items-center gap-2 font-semibold">
              <input type="checkbox" className={claseCasilla} checked={todas} onChange={() => setExcluidas(todas ? new Set(validas.map(v => v.indice)) : new Set())} />
              Seleccionar todo
            </label>
            <span className="ml-auto">
              <strong className="text-violet-600">{elegidas.length}</strong> de <strong>{validas.length}</strong> filas seleccionadas
              {invalidas > 0 && <span className="ml-2 text-red-500">· {invalidas} con teléfono inválido</span>}
            </span>
          </div>
          <Tabla className="text-[0.8rem]">
            <thead>
              <tr><th className="w-8" /><th>Fila</th><th>Teléfono</th><th>Nombre</th><th>Etiquetas</th><th>Notas</th></tr>
            </thead>
            <tbody>
              {vistas.slice(0, FILAS_VISIBLES).map(v => (
                <tr key={v.indice} className={v.revision.ok ? (excluidas.has(v.indice) ? 'bg-gray-50' : 'bg-white') : 'bg-red-50'}>
                  <td>
                    <input type="checkbox" className={claseCasilla} disabled={!v.revision.ok} checked={v.revision.ok && !excluidas.has(v.indice)} onChange={() => alternar(v.indice)} />
                  </td>
                  <td className="text-gray-400">{v.fila}</td>
                  <td className="font-mono">
                    {v.revision.ok ? mostrarTelefono(v.revision.numero) : <span className="text-red-800">{v.telefono || 'vacío'} · {v.revision.error}</span>}
                  </td>
                  <td>{v.nombre}</td>
                  <td>{v.etiquetas}</td>
                  <td className="text-gray-500">{v.notas}</td>
                </tr>
              ))}
            </tbody>
          </Tabla>
          {vistas.length > FILAS_VISIBLES && (
            <p className="py-2.5 text-[0.78rem] text-gray-500">
              Se muestran las primeras {FILAS_VISIBLES} filas. Se importarán todas las filas seleccionadas.
            </p>
          )}
        </div>

        <div className="flex flex-wrap items-center justify-end gap-2.5 border-t border-gray-200 px-6 py-3.5">
          {error && <span className="mr-auto text-[0.82rem] text-red-800">{error}</span>}
          <Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton>
          <Boton variante="violeta" disabled={!elegidas.length || importando} onClick={importar}>
            {importando ? 'Importando...' : `Importar ${elegidas.length} contactos`}
          </Boton>
        </div>
      </div>
    </Fondo>
  )
}

export default function ImportarContactosPage() {
  const [archivo, setArchivo] = useState(null)
  const [separador, setSeparador] = useState(',')
  const [conEncabezado, setConEncabezado] = useState(true)
  const [lectura, setLectura] = useState(null)
  const [mostrarVista, setMostrarVista] = useState(false)
  const [resultado, setResultado] = useState(null)
  const [error, setError] = useState('')

  const leer = (elegido, sep, encabezado) => {
    if (!elegido) return
    setError('')
    if (!/\.(csv|txt)$/i.test(elegido.name)) {
      setError('El archivo debe ser .csv o .txt.')
      return
    }
    if (elegido.size > MAXIMO_MB * 1024 * 1024) {
      setError(`El archivo supera ${MAXIMO_MB} MB.`)
      return
    }
    setArchivo(elegido)
    const lector = new FileReader()
    lector.onload = e => {
      const filas = leerCsv(e.target.result, sep)
      if (!filas.length) {
        setError('El archivo está vacío.')
        setLectura(null)
        return
      }
      const columnas = Math.max(...filas.map(f => f.length))
      setLectura(encabezado
        ? { encabezados: filas[0], filas: filas.slice(1), conEncabezado: true }
        : { encabezados: Array.from({ length: columnas }, (_, i) => `Columna ${i + 1}`), filas, conEncabezado: false })
    }
    lector.readAsText(elegido, 'utf-8')
  }

  const reiniciar = () => {
    setArchivo(null); setLectura(null); setResultado(null); setMostrarVista(false); setError('')
  }

  return (
    <Pagina titulo="Importar contactos desde CSV">

      {resultado && <Resultado resultado={resultado} onOtro={reiniciar} />}

      <div className="grid grid-cols-[repeat(auto-fit,minmax(280px,1fr))] gap-4">
        <Tarjeta titulo="Subir archivo CSV">
          <p className="mb-4 text-[0.82rem] text-gray-500">
            Sube tu archivo con los contactos. Podrás asignar cada columna al campo correcto antes de importar.
          </p>
          <ZonaArchivo archivo={archivo} onArchivo={f => leer(f, separador, conEncabezado)} />
          <div className="mb-4">
            <Etiqueta>Separador de columnas</Etiqueta>
            <select className={claseEntrada} value={separador} onChange={e => { setSeparador(e.target.value); leer(archivo, e.target.value, conEncabezado) }}>
              {SEPARADORES.map(s => <option key={s.valor} value={s.valor}>{s.label}</option>)}
            </select>
          </div>
          <label className="mb-4 flex cursor-pointer items-center gap-2 text-[0.85rem]">
            <input type="checkbox" className={claseCasilla} checked={conEncabezado} onChange={e => { setConEncabezado(e.target.checked); leer(archivo, separador, e.target.checked) }} />
            La primera fila tiene los nombres de las columnas
          </label>
          <AlertBox>{error}</AlertBox>
          <div className="flex flex-wrap gap-2.5">
            <Boton variante="violeta" className="flex-1" disabled={!lectura} onClick={() => setMostrarVista(true)}>
              Vista previa e importar
            </Boton>
            <Boton variante="contorno" onClick={descargarPlantilla}>
              Descargar plantilla
            </Boton>
          </div>
        </Tarjeta>

        <Tarjeta titulo="Formato esperado">
          <p className="mb-3.5 text-[0.82rem] text-gray-500">
            Tu CSV puede tener cualquier columna, las asignas al importar. Formato ideal:
          </p>
          <pre className="mb-4 overflow-x-auto rounded-lg bg-panel px-4 py-3.5 text-[0.78rem] text-gray-700">{`telefono,nombre,etiquetas,notas
0991234567,Juan Pérez,cliente,Interesado
593987654321,María López,"lead,vip",`}</pre>
          <div className="rounded-lg border border-orange-200 bg-orange-50 px-3.5 py-2.5 text-[0.8rem] leading-relaxed text-amber-800">
            <strong>Teléfonos válidos para WhatsApp</strong><br />
            Solo móviles. Ecuador: <code>09XXXXXXXX</code> o <code>5939XXXXXXXX</code>. Otros países con su código.<br />
            Los números fijos se rechazan. Si un teléfono ya existe, se actualizan sus datos.
          </div>
        </Tarjeta>
      </div>

      {mostrarVista && lectura && (
        <VistaPrevia
          archivo={archivo}
          lectura={lectura}
          onCerrar={() => setMostrarVista(false)}
          onImportado={r => { setResultado(r); setMostrarVista(false); setArchivo(null); setLectura(null) }}
        />
      )}
    </Pagina>
  )
}
