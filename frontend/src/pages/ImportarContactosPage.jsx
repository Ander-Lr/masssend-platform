import { useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { sileo } from 'sileo'
import AlertBox from '../components/auth/AlertBox'
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
      className={`zona-archivo${arrastrando ? ' activa' : ''}`}
      onDragOver={e => { e.preventDefault(); setArrastrando(true) }}
      onDragLeave={() => setArrastrando(false)}
      onDrop={e => { e.preventDefault(); setArrastrando(false); onArchivo(e.dataTransfer.files[0]) }}
      onClick={() => entrada.current?.click()}
      role="button"
      tabIndex={0}
      onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') entrada.current?.click() }}
    >
      <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#7c3aed" strokeWidth="1.5" strokeLinecap="round" aria-hidden="true">
        <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" />
      </svg>
      <p style={{ color: '#7c3aed', fontWeight: 600, margin: '10px 0 4px' }}>
        {archivo ? archivo.name : 'Arrastra tu CSV aquí o haz clic para seleccionar'}
      </p>
      <p style={{ fontSize: '0.75rem', color: '#aaa' }}>Formatos .csv o .txt, máximo {MAXIMO_MB} MB</p>
      <input
        ref={entrada}
        type="file"
        accept=".csv,.txt"
        style={{ display: 'none' }}
        onChange={e => { onArchivo(e.target.files[0]); e.target.value = '' }}
      />
    </div>
  )
}

function Resultado({ resultado, onOtro }) {
  return (
    <div className="resultado-importacion">
      <p style={{ fontWeight: 700, color: '#065f46', marginBottom: 8 }}>Importación completada</p>
      <div style={{ display: 'flex', gap: 24, fontSize: '0.88rem', flexWrap: 'wrap' }}>
        <span>Total: <strong>{resultado.total}</strong></span>
        <span style={{ color: '#10b981' }}>Creados: <strong>{resultado.creados}</strong></span>
        <span style={{ color: '#3b82f6' }}>Actualizados: <strong>{resultado.actualizados}</strong></span>
        <span style={{ color: '#ef4444' }}>Rechazados: <strong>{resultado.total_rechazadas}</strong></span>
      </div>
      {resultado.rechazadas.length > 0 && (
        <div className="tabla-contenedor" style={{ marginTop: 14, maxHeight: 240, overflowY: 'auto' }}>
          <table>
            <thead><tr><th>Fila del archivo</th><th>Teléfono</th><th>Motivo</th></tr></thead>
            <tbody>
              {resultado.rechazadas.map((r, i) => (
                <tr key={i}><td>{r.fila}</td><td style={{ fontFamily: 'monospace' }}>{r.telefono || 'vacío'}</td><td style={{ color: '#991b1b' }}>{r.mensaje}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {resultado.total_rechazadas > resultado.rechazadas.length && (
        <p className="texto-suave" style={{ fontSize: '0.78rem', marginTop: 8 }}>
          Se muestran las primeras {resultado.rechazadas.length} filas rechazadas.
        </p>
      )}
      <div style={{ display: 'flex', gap: 10, marginTop: 14 }}>
        <button className="boton" style={{ background: '#065f46', color: '#fff', padding: '8px 20px', fontWeight: 600 }} onClick={onOtro}>Importar otro archivo</button>
        <Link to="/contactos" className="boton boton-secundario" style={{ textDecoration: 'none', padding: '8px 20px' }}>Ver contactos</Link>
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
    <div className="modal-fondo">
      <div className="modal" role="dialog" aria-modal="true" aria-label="Vista previa del archivo" style={{ maxWidth: 920, padding: 0, maxHeight: '90vh', display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '20px 24px 16px', borderBottom: '1px solid #e5e7eb' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
            <div>
              <h2 style={{ fontSize: '1.05rem', fontWeight: 700 }}>Vista previa del archivo</h2>
              <p className="texto-suave" style={{ fontSize: '0.78rem', marginTop: 4 }}>{archivo.name} · {filas.length} filas encontradas</p>
            </div>
            <button className="modal-cerrar" onClick={onCerrar} aria-label="Cerrar">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
            </button>
          </div>
          {columnaTelefono === undefined && (
            <div className="aviso" style={{ background: '#fef3c7', color: '#92400e', marginTop: 12, marginBottom: 0 }}>
              Asigna la columna <strong>Teléfono</strong> para poder importar.
            </div>
          )}
          <p className="titulo-violeta">Asigna cada columna del CSV a un campo</p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
            {encabezados.map((encabezado, i) => (
              <div key={i} style={{ minWidth: 140 }}>
                <div style={{ fontSize: '0.7rem', color: '#888', marginBottom: 3, fontFamily: 'monospace' }}>{encabezado}</div>
                <select
                  className={`selector-columna${asignadas[i] === 'telefono' ? ' telefono' : asignadas[i] ? ' asignada' : ''}`}
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

        <div style={{ flex: 1, overflowY: 'auto', padding: '0 24px' }}>
          <div className="barra-vista-previa">
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontWeight: 600 }}>
              <input type="checkbox" className="casilla" checked={todas} onChange={() => setExcluidas(todas ? new Set(validas.map(v => v.indice)) : new Set())} />
              Seleccionar todo
            </label>
            <span style={{ marginLeft: 'auto' }}>
              <strong style={{ color: '#7c3aed' }}>{elegidas.length}</strong> de <strong>{validas.length}</strong> filas seleccionadas
              {invalidas > 0 && <span style={{ color: '#ef4444', marginLeft: 8 }}>· {invalidas} con teléfono inválido</span>}
            </span>
          </div>
          <table style={{ fontSize: '0.8rem' }}>
            <thead>
              <tr><th style={{ width: 32 }} /><th>Fila</th><th>Teléfono</th><th>Nombre</th><th>Etiquetas</th><th>Notas</th></tr>
            </thead>
            <tbody>
              {vistas.slice(0, FILAS_VISIBLES).map(v => (
                <tr key={v.indice} style={{ background: v.revision.ok ? (excluidas.has(v.indice) ? '#fafafa' : '#fff') : '#fff5f5' }}>
                  <td>
                    <input type="checkbox" className="casilla" disabled={!v.revision.ok} checked={v.revision.ok && !excluidas.has(v.indice)} onChange={() => alternar(v.indice)} />
                  </td>
                  <td style={{ color: '#9ca3af' }}>{v.fila}</td>
                  <td style={{ fontFamily: 'monospace' }}>
                    {v.revision.ok ? mostrarTelefono(v.revision.numero) : <span style={{ color: '#991b1b' }}>{v.telefono || 'vacío'} · {v.revision.error}</span>}
                  </td>
                  <td>{v.nombre}</td>
                  <td>{v.etiquetas}</td>
                  <td style={{ color: '#6b7280' }}>{v.notas}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {vistas.length > FILAS_VISIBLES && (
            <p className="texto-suave" style={{ fontSize: '0.78rem', padding: '10px 0' }}>
              Se muestran las primeras {FILAS_VISIBLES} filas. Se importarán todas las filas seleccionadas.
            </p>
          )}
        </div>

        <div style={{ padding: '14px 24px', borderTop: '1px solid #e5e7eb', display: 'flex', gap: 10, alignItems: 'center', justifyContent: 'flex-end', flexWrap: 'wrap' }}>
          {error && <span style={{ color: '#991b1b', fontSize: '0.82rem', marginRight: 'auto' }}>{error}</span>}
          <button className="boton boton-secundario" onClick={onCerrar}>Cancelar</button>
          <button className="boton" style={{ background: '#7c3aed', color: '#fff' }} disabled={!elegidas.length || importando} onClick={importar}>
            {importando ? 'Importando...' : `Importar ${elegidas.length} contactos`}
          </button>
        </div>
      </div>
    </div>
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
    <div className="pagina" style={{ background: '#f8f9fa' }}>
      <h1 className="pagina-titulo" style={{ marginBottom: 24 }}>Importar contactos desde CSV</h1>

      {resultado && <Resultado resultado={resultado} onOtro={reiniciar} />}

      <div className="rejilla">
        <div className="tarjeta">
          <h2 className="tarjeta-titulo">Subir archivo CSV</h2>
          <p className="texto-suave" style={{ fontSize: '0.82rem', marginBottom: 16 }}>
            Sube tu archivo con los contactos. Podrás asignar cada columna al campo correcto antes de importar.
          </p>
          <ZonaArchivo archivo={archivo} onArchivo={f => leer(f, separador, conEncabezado)} />
          <div className="campo">
            <label>Separador de columnas</label>
            <select className="entrada" value={separador} onChange={e => { setSeparador(e.target.value); leer(archivo, e.target.value, conEncabezado) }}>
              {SEPARADORES.map(s => <option key={s.valor} value={s.valor}>{s.label}</option>)}
            </select>
          </div>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.85rem', marginBottom: 16, cursor: 'pointer' }}>
            <input type="checkbox" className="casilla" checked={conEncabezado} onChange={e => { setConEncabezado(e.target.checked); leer(archivo, separador, e.target.checked) }} />
            La primera fila tiene los nombres de las columnas
          </label>
          <AlertBox>{error}</AlertBox>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <button className="boton" style={{ flex: 1, background: '#7c3aed', color: '#fff' }} disabled={!lectura} onClick={() => setMostrarVista(true)}>
              Vista previa e importar
            </button>
            <button className="boton" style={{ background: '#fff', color: '#7c3aed', border: '1.5px solid #7c3aed', fontWeight: 600 }} onClick={descargarPlantilla}>
              Descargar plantilla
            </button>
          </div>
        </div>

        <div className="tarjeta">
          <h2 className="tarjeta-titulo">Formato esperado</h2>
          <p className="texto-suave" style={{ fontSize: '0.82rem', marginBottom: 14 }}>
            Tu CSV puede tener cualquier columna, las asignas al importar. Formato ideal:
          </p>
          <pre className="ejemplo-csv">{`telefono,nombre,etiquetas,notas
0991234567,Juan Pérez,cliente,Interesado
593987654321,María López,"lead,vip",`}</pre>
          <div className="aviso" style={{ background: '#fff7ed', border: '1px solid #fed7aa', color: '#92400e' }}>
            <strong>Teléfonos válidos para WhatsApp</strong><br />
            Solo móviles. Ecuador: <code>09XXXXXXXX</code> o <code>5939XXXXXXXX</code>. Otros países con su código.<br />
            Los números fijos se rechazan. Si un teléfono ya existe, se actualizan sus datos.
          </div>
        </div>
      </div>

      {mostrarVista && lectura && (
        <VistaPrevia
          archivo={archivo}
          lectura={lectura}
          onCerrar={() => setMostrarVista(false)}
          onImportado={r => { setResultado(r); setMostrarVista(false); setArchivo(null); setLectura(null) }}
        />
      )}
    </div>
  )
}
