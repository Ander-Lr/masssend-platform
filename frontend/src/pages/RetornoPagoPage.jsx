import { useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import AuthCard from '../components/auth/AuthCard'
import AlertBox from '../components/auth/AlertBox'
import PrimaryButton from '../components/auth/PrimaryButton'
import Boton from '../components/ui/Boton'
import { comprasPendientes, confirmarCompra } from '../api/creditos'
import { useAuth } from '../context/AuthContext'
import { recordarDestino } from './auth/pasos'

const MINUTOS_PAYPHONE = 5

// La pasarela vuelve con su referencia en la URL. PayPal agrega ?token=<orden>,
// PayPhone agrega ?id=<transaccion>&clientTransactionId=<referencia>.
function leerRetorno(params) {
  const proveedor = (params.get('provider') || '').toLowerCase()
  if (params.get('cancelled')) return { proveedor, cancelado: true }
  if (params.get('simulada')) return { proveedor, referencia: params.get('simulada'), datos: {} }
  if (proveedor === 'paypal') return { proveedor, referencia: params.get('token'), datos: {} }
  if (proveedor === 'payphone') {
    return { proveedor, referencia: params.get('clientTransactionId'), id: params.get('id'), datos: { id: params.get('id') } }
  }
  return { proveedor }
}

function Copiable({ etiqueta, valor }) {
  const [copiado, setCopiado] = useState(false)
  const copiar = async () => {
    try { await navigator.clipboard.writeText(valor); setCopiado(true) } catch { /* se copia a mano */ }
  }
  return (
    <div className="mb-3 flex items-center gap-2 rounded-lg border border-gray-200 p-3">
      <div className="min-w-0 flex-1">
        <div className="text-[0.78rem] text-gray-500">{etiqueta}</div>
        <code className="break-all text-lg font-semibold">{valor}</code>
      </div>
      <Boton variante="secundario" tamano="sm" onClick={copiar}>{copiado ? 'Copiado' : 'Copiar'}</Boton>
    </div>
  )
}

// PayPhone revierte el cobro si no se confirma a tiempo.
function CuentaRegresiva() {
  const [limite] = useState(() => Date.now() + MINUTOS_PAYPHONE * 60000)
  const [ahora, setAhora] = useState(() => Date.now())
  useEffect(() => {
    const t = setInterval(() => setAhora(Date.now()), 1000)
    return () => clearInterval(t)
  }, [])
  const resta = Math.max(0, Math.round((limite - ahora) / 1000))
  return (
    <p className={`mb-4 text-[0.82rem] ${resta ? 'text-amber-700' : 'text-red-700'}`}>
      {resta
        ? `Confirma antes de ${Math.floor(resta / 60)}:${String(resta % 60).padStart(2, '0')}; si no, PayPhone revierte el cobro.`
        : 'Pasaron 5 minutos: PayPhone pudo revertir el cobro. Haz una compra nueva.'}
    </p>
  )
}

// Sin la compra en este navegador (por ejemplo, al probar con Postman) se muestran
// los datos que hacen falta para confirmar a mano.
function DatosManuales({ retorno }) {
  if (retorno.proveedor === 'payphone') {
    if (!retorno.id) return <AlertBox type="advertencia">PayPhone no envió un id: el pago se canceló. Vuelve a iniciar la compra.</AlertBox>
    return (
      <>
        <AlertBox type="success">Pago realizado en PayPhone. Copia el id y confírmalo (en Postman, variable payphoneId y luego Confirmar PayPhone).</AlertBox>
        <Copiable etiqueta="id (payphoneId)" valor={retorno.id} />
        {retorno.referencia && <p className="mb-2 text-[0.82rem] text-gray-500">Referencia de la compra: {retorno.referencia}</p>}
        <CuentaRegresiva />
      </>
    )
  }
  if (retorno.proveedor === 'paypal') {
    return (
      <>
        <AlertBox type="success">Pago aprobado en PayPal. Ya puedes ejecutar Confirmar.</AlertBox>
        {retorno.referencia && <Copiable etiqueta="Orden de PayPal" valor={retorno.referencia} />}
      </>
    )
  }
  return <AlertBox>No se reconoce la pasarela de este pago.</AlertBox>
}

function estadoInicial(retorno, hayUsuario) {
  if (retorno.cancelado) return { tipo: 'error', texto: 'Cancelaste el pago. No se realizó ningún cargo.' }
  const compra = retorno.referencia && comprasPendientes.buscar(retorno.referencia)
  if (!compra) return { tipo: 'manual' }
  if (!hayUsuario) return { tipo: 'sin-sesion', compra }
  return { tipo: 'cargando', texto: 'Confirmando tu pago, un momento...', compra }
}

export default function RetornoPagoPage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const { usuario, cargando } = useAuth()
  const [retorno] = useState(() => leerRetorno(params))
  const [estado, setEstado] = useState(null)
  const enviado = useRef(false)
  const actual = estado || (cargando ? { tipo: 'cargando', texto: 'Cargando...' } : estadoInicial(retorno, Boolean(usuario)))

  useEffect(() => {
    // Confirmar dos veces no acredita doble, pero se evita la llamada repetida.
    if (cargando || !usuario || estado || enviado.current) return
    const compra = retorno.referencia && comprasPendientes.buscar(retorno.referencia)
    if (retorno.cancelado || !compra) return
    enviado.current = true
    confirmarCompra(compra.id, retorno.datos)
      .then(r => {
        comprasPendientes.quitar(retorno.referencia)
        setEstado(r.estado === 'aprobada'
          ? { tipo: 'exito', texto: r.ya_procesada ? `Este pago ya estaba confirmado. Tus ${r.creditos} créditos ya están en tu cuenta.` : `Pago aprobado. Se acreditaron ${r.creditos} créditos a tu cuenta.` }
          : { tipo: 'error', texto: 'La pasarela no aprobó el pago. No se acreditaron créditos.' })
      })
      .catch(err => setEstado({ tipo: 'error', texto: err.mensajeUsuario }))
  }, [cargando, usuario, estado, retorno])

  const iniciarSesion = () => {
    recordarDestino(window.location.pathname + window.location.search)
    navigate('/login')
  }

  return (
    <AuthCard title="Estado del pago" ancho="w-[460px]">
      {actual.tipo === 'cargando' && <p className="mb-4 text-center text-[0.88rem] text-gray-500">{actual.texto}</p>}
      {actual.tipo === 'exito' && <AlertBox type="success">{actual.texto}</AlertBox>}
      {actual.tipo === 'error' && <AlertBox>{actual.texto}</AlertBox>}
      {actual.tipo === 'manual' && <DatosManuales retorno={retorno} />}
      {actual.tipo === 'sin-sesion' && (
        <>
          <AlertBox type="info">Tu sesión se cerró mientras pagabas. Inicia sesión para confirmar la compra y recibir tus créditos.</AlertBox>
          {retorno.proveedor === 'payphone' && <CuentaRegresiva />}
          <PrimaryButton type="button" onClick={iniciarSesion}>Iniciar sesión y confirmar</PrimaryButton>
        </>
      )}
      {usuario && actual.tipo !== 'sin-sesion' && (
        <PrimaryButton type="button" disabled={actual.tipo === 'cargando'} onClick={() => navigate('/creditos', { replace: true })}>
          Volver a Créditos
        </PrimaryButton>
      )}
    </AuthCard>
  )
}
