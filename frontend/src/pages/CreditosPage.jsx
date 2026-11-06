import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import AlertBox from '../components/auth/AlertBox'
import Boton from '../components/ui/Boton'
import Estadistica, { Estadisticas } from '../components/ui/Estadistica'
import Pagina from '../components/ui/Pagina'
import Insignia from '../components/ui/Insignia'
import Tarjeta from '../components/ui/Tarjeta'
import { ContenedorTabla, Tabla } from '../components/ui/Tabla'
import { comprasPendientes, iniciarCompra, movimientos, paquetes, saldo } from '../api/creditos'

const PASARELAS = [
  { id: 'PAYPAL', label: 'Pagar con PayPal', clase: 'bg-paypal hover:brightness-110' },
  { id: 'PAYPHONE', label: 'Pagar con PayPhone', clase: 'bg-payphone hover:brightness-110' },
]

const fecha = valor => new Date(valor).toLocaleString('es-EC', { dateStyle: 'medium', timeStyle: 'short' })

function Saldo({ datos }) {
  const tarjetas = [
    { label: 'Disponible', valor: datos?.disponible, color: 'verde' },
    { label: 'Reservado en campañas', valor: datos?.reservado, color: 'azul' },
    { label: 'Saldo total', valor: datos?.saldo, color: 'normal' },
  ]
  return (
    <Estadisticas className="max-w-[760px]">
      {tarjetas.map(t => <Estadistica key={t.label} valor={datos ? t.valor : '...'} etiqueta={t.label} color={t.color} />)}
    </Estadisticas>
  )
}

function Historial() {
  const [lista, setLista] = useState([])
  const [cursor, setCursor] = useState(null)
  const [tieneMas, setTieneMas] = useState(false)
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState('')

  const recibir = useCallback((r, anexar) => {
    setLista(actual => (anexar ? [...actual, ...r.datos] : r.datos))
    setCursor(r.pagina.siguiente_cursor)
    setTieneMas(r.pagina.tiene_mas)
  }, [])

  useEffect(() => {
    movimientos(null)
      .then(r => recibir(r, false))
      .catch(err => setError(err.mensajeUsuario))
      .finally(() => setCargando(false))
  }, [recibir])

  const verMas = async () => {
    setCargando(true)
    try {
      recibir(await movimientos(cursor), true)
    } catch (err) {
      setError(err.mensajeUsuario)
    } finally {
      setCargando(false)
    }
  }

  return (
    <ContenedorTabla titulo="Movimientos" className="max-w-[760px]">
      {error && <div className="px-5 pt-3"><AlertBox>{error}</AlertBox></div>}
      <Tabla>
        <thead>
          <tr><th>Fecha</th><th>Detalle</th><th className="!text-right">Créditos</th></tr>
        </thead>
        <tbody>
          {lista.map((m, i) => (
            <tr key={`${m.fecha}-${i}`}>
              <td className="whitespace-nowrap text-gray-500">{fecha(m.fecha)}</td>
              <td>
                <Insignia color={m.tipo === 'compra' ? 'azul' : 'gris'} className="mr-2">{m.tipo === 'compra' ? 'Compra' : 'Consumo'}</Insignia>
                {m.detalle}
              </td>
              <td className={`text-right font-bold ${m.tipo === 'compra' ? 'text-emerald-500' : 'text-red-500'}`}>
                {m.tipo === 'compra' ? '+' : '-'}{Math.abs(m.creditos)}
              </td>
            </tr>
          ))}
          {!cargando && lista.length === 0 && (
            <tr><td colSpan={3} className="!py-6 text-center text-gray-400">Aún no tienes movimientos.</td></tr>
          )}
        </tbody>
      </Tabla>
      {(tieneMas || cargando) && (
        <div className="p-3.5 text-center">
          <Boton variante="secundario" disabled={cargando} onClick={verMas}>{cargando ? 'Cargando...' : 'Ver más'}</Boton>
        </div>
      )}
    </ContenedorTabla>
  )
}

// 1 credito = 1 mensaje enviado. La pasarela devuelve al usuario a /billing/return.
export default function CreditosPage() {
  const navigate = useNavigate()
  const [lista, setLista] = useState([])
  const [datosSaldo, setDatosSaldo] = useState(null)
  const [error, setError] = useState('')
  const [pagando, setPagando] = useState('')

  useEffect(() => {
    Promise.all([paquetes(), saldo()])
      .then(([p, s]) => { setLista(p.datos); setDatosSaldo(s) })
      .catch(err => setError(err.mensajeUsuario))
  }, [])

  const comprar = async (paqueteId, pasarela) => {
    setError('')
    setPagando(`${paqueteId}-${pasarela}`)
    try {
      const compra = await iniciarCompra(paqueteId, pasarela)
      comprasPendientes.guardar(compra)
      // Una pasarela simulada no tiene pagina de pago: se confirma directamente.
      if (compra.referencia.startsWith('FALSA-')) {
        navigate(`/billing/return?provider=${pasarela.toLowerCase()}&simulada=${encodeURIComponent(compra.referencia)}`)
        return
      }
      window.location.assign(compra.url_pago)
    } catch (err) {
      setError(err.mensajeUsuario)
      setPagando('')
    }
  }

  return (
    <Pagina
      titulo="Créditos"
      subtitulo="1 crédito equivale a 1 mensaje enviado en una campaña. Toda cuenta nueva recibe créditos de bienvenida para probar."
      fondo="bg-lienzo"
    >
      <Saldo datos={datosSaldo} />
      {error && <div className="max-w-[760px]"><AlertBox>{error}</AlertBox></div>}

      <Tarjeta titulo="Paquetes disponibles" className="mb-6 max-w-[760px]">
        {lista.length === 0 && !error && <p className="mt-3 text-[0.88rem] text-gray-500">Cargando paquetes...</p>}
        <div className="mt-3.5 flex flex-col gap-3">
          {lista.map(p => (
            <div key={p.id} className="flex flex-wrap items-center justify-between gap-4 rounded-xl border-[1.5px] border-gray-200 px-5 py-[18px]">
              <div>
                <div className="font-bold">{p.nombre}</div>
                <div className="text-[0.88rem] text-gray-500">{p.creditos} créditos · ${p.precio} {p.moneda}</div>
              </div>
              <div className="flex flex-wrap gap-2">
                {PASARELAS.map(g => (
                  <button key={g.id} disabled={Boolean(pagando)} onClick={() => comprar(p.id, g.id)}
                    className={`rounded-lg px-4 py-[9px] text-[0.85rem] font-bold text-white disabled:opacity-60 ${g.clase}`}>
                    {pagando === `${p.id}-${g.id}` ? 'Redirigiendo...' : g.label}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      </Tarjeta>

      <Historial />
    </Pagina>
  )
}
