import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import AuthCard from '../../components/auth/AuthCard'
import { CodigoField } from '../../components/auth/FormField'
import AlertBox from '../../components/auth/AlertBox'
import PrimaryButton from '../../components/auth/PrimaryButton'
import LinkButton from '../../components/auth/LinkButton'
import { useAuth } from '../../context/AuthContext'
import { tomarDestino } from './pasos'

// Segundo paso del inicio de sesion para cuentas que ya tienen el doble factor.
export default function TotpPage() {
  const { desafio, validarTotp, cancelarDesafio } = useAuth()
  const navigate = useNavigate()
  const [codigo, setCodigo] = useState('')
  const [error, setError] = useState('')
  const [cargando, setCargando] = useState(false)

  if (desafio?.siguiente !== 'totp') return <Navigate to="/login" replace />

  const enviar = async e => {
    e.preventDefault()
    setError('')
    setCargando(true)
    try {
      await validarTotp(codigo)
      navigate(tomarDestino(), { replace: true })
    } catch (err) {
      setError(err.estado === 401
        ? 'El código no es válido o la verificación venció. Si pasaron más de 5 minutos, vuelve a iniciar sesión.'
        : err.mensajeUsuario)
      setCodigo('')
      setCargando(false)
    }
  }

  const cancelar = () => {
    cancelarDesafio()
    navigate('/login')
  }

  return (
    <AuthCard title="Verificación en dos pasos" subtitle={`Abre tu aplicación de autenticación y escribe el código de ${desafio.correo || 'tu cuenta'}`}>
      <form onSubmit={enviar}>
        <CodigoField label="Código del autenticador" value={codigo} onChange={setCodigo} />
        <AlertBox>{error}</AlertBox>
        <PrimaryButton loading={cargando} disabled={codigo.length !== 6}>
          {cargando ? 'Verificando...' : 'Confirmar'}
        </PrimaryButton>
      </form>
      <div className="mt-[18px] text-center">
        <LinkButton onClick={cancelar}>Cancelar</LinkButton>
      </div>
    </AuthCard>
  )
}
