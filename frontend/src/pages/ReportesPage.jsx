import { useEffect, useState } from 'react'
import AlertBox from '../components/auth/AlertBox'
import { reporte as pedirReporte } from '../api/envio'
import { ESTADOS } from '../api/campanas'

const MAX_DIAS = 366
const iso = fecha => fecha.toISOString().slice(0, 10)
const haceDias = dias => { const d = new Date(); d.setDate(d.getDate() - dias); return iso(d) }
// La API solo devuelve los dias con mensajes: se completan los demas con cero.
function completarDias(porDia, desde, hasta) {
  const conDatos = Object.fromEntries(porDia.map(d => [d.dia, d]))
  const dias = []
  for (let d = new Date(`${desde}T00:00:00`); iso2(d) <= hasta; d.setDate(d.getDate() + 1)) {
    const clave = iso2(d)
    dias.push(conDatos[clave] || { dia: clave, enviados: 0, recibidos: 0 })
  }
  return dias
}
const iso2 = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
const diaCorto = dia => new Date(`${dia}T00:00:00`).toLocaleDateString('es-EC', { day: '2-digit', month: 'short' })

function Tasa({ titulo, valor, color, detalle }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.82rem', marginBottom: 6 }}>
        <span style={{ fontWeight: 600 }}>{titulo}</span>
        <span style={{ fontWeight: 700, color }}>{valor}%</span>
      </div>
      <div className="progreso-pista"><div className="progreso-relleno" style={{ width: `${Math.min(valor, 100)}%`, background: color }} /></div>
      <p className="texto-suave" style={{ fontSize: '0.72rem', marginTop: 4 }}>{detalle}</p>
    </div>
  )
}

// Barras de enviados y recibidos por dia; con muchos dias se muestran solo algunas fechas.
function GraficaBarras({ datos }) {
  const conActividad = datos.some(d => d.enviados || d.recibidos)
  if (!conActividad) {
    return <div className="grafica-vacia">Sin mensajes en el periodo seleccionado</div>
  }
  const maximo = Math.max(...datos.map(d => Math.max(d.enviados, d.recibidos)), 1)
  const cadaCuanto = Math.ceil(datos.length / 15)
  return (
    <>
      <div className="grafica" role="img" aria-label="Mensajes enviados y recibidos por día">
        {datos.map((d, i) => (
          <div key={d.dia} className="grafica-dia" title={`${diaCorto(d.dia)}: ${d.enviados} enviados, ${d.recibidos} recibidos`}>
            <div className="grafica-barras">
              <div style={{ height: `${(d.enviados / maximo) * 100}%`, background: '#6366f1', minHeight: d.enviados ? 4 : 0 }} />
              <div style={{ height: `${(d.recibidos / maximo) * 100}%`, background: '#10b981', minHeight: d.recibidos ? 4 : 0 }} />
            </div>
            <span>{i % cadaCuanto === 0 ? diaCorto(d.dia) : ''}</span>
          </div>
        ))}
      </div>
      <div className="leyenda">
        <span><i style={{ background: '#6366f1' }} />Enviados</span>
        <span><i style={{ background: '#10b981' }} />Recibidos</span>
      </div>
    </>
  )
}

export default function ReportesPage() {
  const [desde, setDesde] = useState(() => haceDias(29))
  const [hasta, setHasta] = useState(() => iso(new Date()))
  const [consulta, setConsulta] = useState({ desde: haceDias(29), hasta: iso(new Date()) })
  const [datos, setDatos] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let vigente = true
    pedirReporte(consulta)
      .then(r => { if (vigente) { setDatos(r); setError('') } })
      .catch(err => vigente && setError(err.mensajeUsuario))
    return () => { vigente = false }
  }, [consulta])

  const aplicar = e => {
    e.preventDefault()
    const dias = (new Date(hasta) - new Date(desde)) / 86400000
    if (dias < 0) { setError('La fecha inicial debe ser anterior a la final.'); return }
    if (dias >= MAX_DIAS) { setError('El periodo no puede superar un año.'); return }
    setConsulta({ desde, hasta })
  }

  const rapido = dias => {
    const nuevo = { desde: haceDias(dias - 1), hasta: iso(new Date()) }
    setDesde(nuevo.desde); setHasta(nuevo.hasta); setConsulta(nuevo)
  }

  const r = datos?.resumen
  const tarjetas = r ? [
    { label: 'Enviados', valor: r.enviados, clase: 'purple' },
    { label: 'Entregados', valor: r.entregados, clase: 'blue' },
    { label: 'Leídos', valor: r.leidos, clase: 'green' },
    { label: 'Fallidos', valor: r.fallidos, clase: 'red' },
    { label: 'Pendientes', valor: r.pendientes, clase: '' },
    { label: 'Respuestas recibidas', valor: r.recibidos, clase: 'green' },
  ] : []

  return (
    <div className="pagina" style={{ background: '#f8f9fa' }}>
      <h1 className="pagina-titulo" style={{ marginBottom: 20 }}>Reportes de mensajería</h1>

      <form className="filtros" style={{ alignItems: 'center' }} onSubmit={aplicar}>
        <label className="texto-suave" style={{ fontSize: '0.82rem' }}>Desde</label>
        <input type="date" className="entrada" value={desde} max={hasta} onChange={e => setDesde(e.target.value)} />
        <label className="texto-suave" style={{ fontSize: '0.82rem' }}>Hasta</label>
        <input type="date" className="entrada" value={hasta} min={desde} max={iso(new Date())} onChange={e => setHasta(e.target.value)} />
        <button type="submit" className="boton boton-primario" style={{ padding: '7px 22px' }}>Aplicar</button>
        <div style={{ display: 'flex', gap: 6 }}>
          {[7, 30, 90].map(d => <button type="button" key={d} className="pestana" onClick={() => rapido(d)}>{d} días</button>)}
        </div>
      </form>

      <AlertBox>{error}</AlertBox>
      {!datos && !error && <div style={{ textAlign: 'center', color: '#aaa', padding: 40 }}>Cargando reporte...</div>}

      {datos && (
        <>
          <div className="stats-grid">
            {tarjetas.map(t => (
              <div key={t.label} className={`stat-card ${t.clase}`}>
                <div className="stat-num">{t.valor}</div>
                <div className="stat-label">{t.label}</div>
              </div>
            ))}
          </div>

          <div className="rejilla" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', alignItems: 'start', marginBottom: 16 }}>
            <div className="tarjeta" style={{ gridColumn: 'span 2', minWidth: 0 }}>
              <h2 className="tarjeta-titulo" style={{ marginBottom: 16 }}>Actividad por día</h2>
              <GraficaBarras datos={completarDias(datos.por_dia, datos.desde, datos.hasta)} />
            </div>
            <div className="tarjeta">
              <h2 className="tarjeta-titulo" style={{ marginBottom: 16 }}>Efectividad</h2>
              <Tasa titulo="Tasa de entrega" valor={r.tasa_entrega} color="#3b82f6" detalle="Mensajes que llegaron al teléfono del contacto." />
              <Tasa titulo="Tasa de lectura" valor={r.tasa_lectura} color="#10b981" detalle="Mensajes que el contacto abrió." />
            </div>
          </div>

          <div className="rejilla" style={{ alignItems: 'start' }}>
            <div className="tarjeta">
              <h2 className="tarjeta-titulo" style={{ marginBottom: 12 }}>Campañas</h2>
              {Object.keys(datos.campanas).length === 0 && <p className="texto-suave">Aún no tienes campañas.</p>}
              {Object.entries(datos.campanas).map(([estado, total]) => (
                <div key={estado} className="fila-resumen">
                  <span className={`insignia insignia-${ESTADOS[estado]?.clase || 'gris'}`}>{ESTADOS[estado]?.label || estado}</span>
                  <strong>{total}</strong>
                </div>
              ))}
            </div>
            <div className="tarjeta">
              <h2 className="tarjeta-titulo" style={{ marginBottom: 12 }}>Contactos</h2>
              <div className="fila-resumen"><span>Total</span><strong>{datos.contactos.total}</strong></div>
              <div className="fila-resumen"><span>Activos</span><strong style={{ color: '#10b981' }}>{datos.contactos.total - datos.contactos.dados_de_baja}</strong></div>
              <div className="fila-resumen"><span>Dados de baja</span><strong style={{ color: '#ef4444' }}>{datos.contactos.dados_de_baja}</strong></div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
