import { useEffect, useState } from 'react'
import AlertBox from '../components/auth/AlertBox'
import Boton from '../components/ui/Boton'
import Estadistica, { Estadisticas } from '../components/ui/Estadistica'
import Insignia from '../components/ui/Insignia'
import Pagina, { Vacio } from '../components/ui/Pagina'
import Progreso from '../components/ui/Progreso'
import Tarjeta from '../components/ui/Tarjeta'
import { claseFiltro } from '../components/ui/Campo'
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

function Tasa({ titulo, valor, color, clase, detalle }) {
  return (
    <div className="mb-4">
      <div className="mb-1.5 flex justify-between text-[0.82rem]">
        <span className="font-semibold">{titulo}</span>
        <span className={`font-bold ${clase}`}>{valor}%</span>
      </div>
      <Progreso porcentaje={valor} color={color} />
      <p className="mt-1 text-[0.72rem] text-gray-500">{detalle}</p>
    </div>
  )
}

// Barras de enviados y recibidos por dia; con muchos dias se muestran solo algunas fechas.
function GraficaBarras({ datos }) {
  const conActividad = datos.some(d => d.enviados || d.recibidos)
  if (!conActividad) {
    return <div className="flex h-[170px] items-center justify-center text-[0.85rem] text-gray-300">Sin mensajes en el periodo seleccionado</div>
  }
  const maximo = Math.max(...datos.map(d => Math.max(d.enviados, d.recibidos)), 1)
  const cadaCuanto = Math.ceil(datos.length / 15)
  // La altura de cada barra depende de los datos: es el unico estilo calculado en linea.
  const alto = valor => ({ height: `${(valor / maximo) * 100}%` })
  return (
    <>
      <div className="flex h-[170px] items-end gap-1 overflow-x-auto overflow-y-hidden" role="img" aria-label="Mensajes enviados y recibidos por día">
        {datos.map((d, i) => (
          <div key={d.dia} className="flex min-w-3.5 flex-1 flex-col items-center gap-1" title={`${diaCorto(d.dia)}: ${d.enviados} enviados, ${d.recibidos} recibidos`}>
            <div className="flex h-[140px] w-full items-end gap-0.5">
              <div className={`flex-1 rounded-t-[3px] bg-indigo-500 transition-[height] ${d.enviados ? 'min-h-1' : ''}`} style={alto(d.enviados)} />
              <div className={`flex-1 rounded-t-[3px] bg-emerald-500 transition-[height] ${d.recibidos ? 'min-h-1' : ''}`} style={alto(d.recibidos)} />
            </div>
            <span className="h-3.5 whitespace-nowrap text-[0.62rem] text-gray-400">{i % cadaCuanto === 0 ? diaCorto(d.dia) : ''}</span>
          </div>
        ))}
      </div>
      <div className="mt-2.5 flex gap-4 text-[0.75rem] text-gray-500">
        <span className="flex items-center gap-1.5"><i className="size-2.5 rounded-sm bg-indigo-500" />Enviados</span>
        <span className="flex items-center gap-1.5"><i className="size-2.5 rounded-sm bg-emerald-500" />Recibidos</span>
      </div>
    </>
  )
}

function Fila({ etiqueta, children }) {
  return <div className="flex items-center justify-between border-b border-gray-100 py-2 text-[0.85rem] last:border-b-0">{etiqueta}{children}</div>
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
    { label: 'Enviados', valor: r.enviados, color: 'morado' },
    { label: 'Entregados', valor: r.entregados, color: 'azul' },
    { label: 'Leídos', valor: r.leidos, color: 'verde' },
    { label: 'Fallidos', valor: r.fallidos, color: 'rojo' },
    { label: 'Pendientes', valor: r.pendientes, color: 'normal' },
    { label: 'Respuestas recibidas', valor: r.recibidos, color: 'verde' },
  ] : []

  return (
    <Pagina titulo="Reportes de mensajería">
      <form className="mb-[18px] flex flex-wrap items-center gap-2.5" onSubmit={aplicar}>
        <label className="text-[0.82rem] text-gray-500">Desde</label>
        <input type="date" className={claseFiltro} value={desde} max={hasta} onChange={e => setDesde(e.target.value)} />
        <label className="text-[0.82rem] text-gray-500">Hasta</label>
        <input type="date" className={claseFiltro} value={hasta} min={desde} max={iso(new Date())} onChange={e => setHasta(e.target.value)} />
        <Boton type="submit" className="px-[22px] py-[7px]">Aplicar</Boton>
        <div className="flex gap-1.5">
          {[7, 30, 90].map(d => (
            <button type="button" key={d} onClick={() => rapido(d)}
              className="rounded-full border border-gray-200 bg-white px-3.5 py-1.5 text-[0.82rem] text-gray-700 hover:border-gray-300">
              {d} días
            </button>
          ))}
        </div>
      </form>

      <AlertBox>{error}</AlertBox>
      {!datos && !error && <Vacio>Cargando reporte...</Vacio>}

      {datos && (
        <>
          <Estadisticas>
            {tarjetas.map(t => <Estadistica key={t.label} valor={t.valor} etiqueta={t.label} color={t.color} />)}
          </Estadisticas>

          <div className="mb-4 grid items-start gap-4 lg:grid-cols-3">
            <Tarjeta titulo="Actividad por día" className="min-w-0 lg:col-span-2">
              <div className="mt-4"><GraficaBarras datos={completarDias(datos.por_dia, datos.desde, datos.hasta)} /></div>
            </Tarjeta>
            <Tarjeta titulo="Efectividad">
              <div className="mt-4">
                <Tasa titulo="Tasa de entrega" valor={r.tasa_entrega} color="#3b82f6" clase="text-blue-500" detalle="Mensajes que llegaron al teléfono del contacto." />
                <Tasa titulo="Tasa de lectura" valor={r.tasa_lectura} color="#10b981" clase="text-emerald-500" detalle="Mensajes que el contacto abrió." />
              </div>
            </Tarjeta>
          </div>

          <div className="grid items-start gap-4 md:grid-cols-2">
            <Tarjeta titulo="Campañas">
              <div className="mt-3">
                {Object.keys(datos.campanas).length === 0 && <p className="text-[0.88rem] text-gray-500">Aún no tienes campañas.</p>}
                {Object.entries(datos.campanas).map(([estado, total]) => (
                  <Fila key={estado} etiqueta={<Insignia color={ESTADOS[estado]?.clase}>{ESTADOS[estado]?.label || estado}</Insignia>}>
                    <strong>{total}</strong>
                  </Fila>
                ))}
              </div>
            </Tarjeta>
            <Tarjeta titulo="Contactos">
              <div className="mt-3">
                <Fila etiqueta="Total"><strong>{datos.contactos.total}</strong></Fila>
                <Fila etiqueta="Activos"><strong className="text-emerald-500">{datos.contactos.total - datos.contactos.dados_de_baja}</strong></Fila>
                <Fila etiqueta="Dados de baja"><strong className="text-red-500">{datos.contactos.dados_de_baja}</strong></Fila>
              </div>
            </Tarjeta>
          </div>
        </>
      )}
    </Pagina>
  )
}
