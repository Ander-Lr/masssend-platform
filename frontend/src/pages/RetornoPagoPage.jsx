import { useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import AuthCard from '../components/auth/AuthCard'
import AlertBox from '../components/auth/AlertBox'
import PrimaryButton from '../components/auth/PrimaryButton'
import { comprasPendientes, confirmarCompra } from '../api/creditos'

// La pasarela vuelve con su referencia en la URL. PayPal agrega ?token=<orden>,
// PayPhone agrega ?id=<transaccion>&clientTransactionId=<referencia>.
function leerRetorno(params) {
  const proveedor = (params.get('provider') || '').toLowerCase()
  if (params.get('cancelled')) return { cancelado: true }
  if (params.get('simulada')) return { referencia: params.get('simulada'), datos: {} }
  if (proveedor === 'paypal') return { referencia: params.get('token'), datos: {} }
  if (proveedor === 'payphone') {
    return { referencia: params.get('clientTransactionId'), datos: { id: params.get('id') } }
  }
  return {}
}

function estadoInicial(params) {
  const retorno = leerRetorno(params)
  if (retorno.cancelado) return { tipo: 'error', texto: 'Cancelaste el pago. No se realizó ningún cargo.' }
  const compra = retorno.referencia && comprasPendientes.buscar(retorno.referencia)
  if (!compra) {
    return { tipo: 'error', texto: 'No se encontró la compra de este pago en este navegador. Si se realizó el cargo, revisa tu saldo en Créditos.' }
  }
  return { tipo: 'cargando', texto: 'Confirmando tu pago, un momento...', compra, retorno }
}

export default function RetornoPagoPage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const [estado, setEstado] = useState(() => estadoInicial(params))
  const enviado = useRef(false)

  useEffect(() => {
    // Confirmar dos veces no acredita doble, pero se evita la llamada repetida.
    if (estado.tipo !== 'cargando' || enviado.current) return
    enviado.current = true
    const { compra, retorno } = estado
    confirmarCompra(compra.id, retorno.datos)
      .then(r => {
        comprasPendientes.quitar(retorno.referencia)
        setEstado(r.estado === 'aprobada'
          ? { tipo: 'exito', texto: r.ya_procesada ? `Este pago ya estaba confirmado. Tus ${r.creditos} créditos ya están en tu cuenta.` : `Pago aprobado. Se acreditaron ${r.creditos} créditos a tu cuenta.` }
          : { tipo: 'error', texto: 'La pasarela no aprobó el pago. No se acreditaron créditos.' })
      })
      .catch(err => setEstado({ tipo: 'error', texto: err.mensajeUsuario }))
  }, [estado])

  return (
    <AuthCard title="Estado del pago" ancho="w-[440px]">
      {estado.tipo === 'cargando' && <p className="mb-4 text-center text-[0.88rem] text-gray-500">{estado.texto}</p>}
      {estado.tipo === 'exito' && <AlertBox type="success">{estado.texto}</AlertBox>}
      {estado.tipo === 'error' && <AlertBox>{estado.texto}</AlertBox>}
      <PrimaryButton type="button" disabled={estado.tipo === 'cargando'} onClick={() => navigate('/creditos', { replace: true })}>
        Volver a Créditos
      </PrimaryButton>
    </AuthCard>
  )
}
