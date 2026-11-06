import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import AlertBox from '../components/auth/AlertBox'
import { comprasPendientes, iniciarCompra, movimientos, paquetes, saldo } from '../api/creditos'

const PASARELAS = [
  { id: 'PAYPAL', label: 'Pagar con PayPal', color: '#0070ba' },
  { id: 'PAYPHONE', label: 'Pagar con PayPhone', color: '#00a6c0' },
]

const fecha = valor => new Date(valor).toLocaleString('es-EC', { dateStyle: 'medium', timeStyle: 'short' })

function Saldo({ datos }) {
  const tarjetas = [
    { label: 'Disponible', valor: datos?.disponible, clase: 'green' },
    { label: 'Reservado en campañas', valor: datos?.reservado, clase: 'blue' },
    { label: 'Saldo total', valor: datos?.saldo, clase: '' },
  ]
  return (
    <div className="stats-grid" style={{ maxWidth: 760 }}>
      {tarjetas.map(t => (
        <div key={t.label} className={`stat-card ${t.clase}`}>
          <div className="stat-num">{datos ? t.valor : '...'}</div>
          <div className="stat-label">{t.label}</div>
        </div>
      ))}
    </div>
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
    <div className="messages-table" style={{ maxWidth: 760 }}>
      <h2>Movimientos</h2>
      {error && <div style={{ padding: '12px 20px' }}><AlertBox>{error}</AlertBox></div>}
      <table>
        <thead>
          <tr><th>Fecha</th><th>Detalle</th><th style={{ textAlign: 'right' }}>Créditos</th></tr>
        </thead>
        <tbody>
          {lista.map((m, i) => (
            <tr key={`${m.fecha}-${i}`}>
              <td style={{ whiteSpace: 'nowrap', color: '#6b7280' }}>{fecha(m.fecha)}</td>
              <td>
                <span className={`status-pill ${m.tipo === 'compra' ? 'pill-delivered' : 'pill-sent'}`} style={{ marginRight: 8 }}>
                  {m.tipo === 'compra' ? 'Compra' : 'Consumo'}
                </span>
                {m.detalle}
              </td>
              <td style={{ textAlign: 'right', fontWeight: 700, color: m.tipo === 'compra' ? '#10b981' : '#ef4444' }}>
                {m.tipo === 'compra' ? '+' : '-'}{Math.abs(m.creditos)}
              </td>
            </tr>
          ))}
          {!cargando && lista.length === 0 && (
            <tr><td colSpan={3} style={{ textAlign: 'center', color: '#9ca3af', padding: 24 }}>Aún no tienes movimientos.</td></tr>
          )}
        </tbody>
      </table>
      {(tieneMas || cargando) && (
        <div style={{ padding: 14, textAlign: 'center' }}>
          <button className="boton boton-secundario" disabled={cargando} onClick={verMas}>
            {cargando ? 'Cargando...' : 'Ver más'}
          </button>
        </div>
      )}
    </div>
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
    <div className="pagina">
      <div className="pagina-encabezado">
        <div>
          <h1 className="pagina-titulo">Créditos</h1>
          <p className="pagina-subtitulo">
            1 crédito equivale a 1 mensaje enviado en una campaña. Toda cuenta nueva recibe créditos de bienvenida para probar.
          </p>
        </div>
      </div>

      <Saldo datos={datosSaldo} />
      {error && <div style={{ maxWidth: 760 }}><AlertBox>{error}</AlertBox></div>}

      <div className="tarjeta" style={{ maxWidth: 760, marginBottom: 24 }}>
        <h2 className="tarjeta-titulo" style={{ marginBottom: 14 }}>Paquetes disponibles</h2>
        {lista.length === 0 && !error && <p className="texto-suave">Cargando paquetes...</p>}
        {lista.map(p => (
          <div key={p.id} className="paquete">
            <div>
              <div style={{ fontWeight: 700 }}>{p.nombre}</div>
              <div className="texto-suave">{p.creditos} créditos · ${p.precio} {p.moneda}</div>
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {PASARELAS.map(g => {
                const clave = `${p.id}-${g.id}`
                return (
                  <button key={g.id} className="boton" style={{ background: g.color, color: '#fff', padding: '9px 16px', fontSize: '0.85rem' }}
                    disabled={Boolean(pagando)} onClick={() => comprar(p.id, g.id)}>
                    {pagando === clave ? 'Redirigiendo...' : g.label}
                  </button>
                )
              })}
            </div>
          </div>
        ))}
      </div>

      <Historial />
    </div>
  )
}
