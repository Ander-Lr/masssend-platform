import { Navigate, useNavigate } from 'react-router-dom'
import AuthCard from '../../components/auth/AuthCard'
import MfaEnrolamiento from '../../components/auth/MfaEnrolamiento'
import LinkButton from '../../components/auth/LinkButton'
import { useAuth } from '../../context/AuthContext'
import { tomarDestino } from './pasos'

// El doble factor es obligatorio: quien no lo tiene lo activa antes de entrar.
export default function EnrolarMfaPage() {
  const { desafio, completarSesion, cancelarDesafio } = useAuth()
  const navigate = useNavigate()

  if (desafio?.siguiente !== 'activar_mfa') return <Navigate to="/login" replace />

  const alActivar = async par => {
    await completarSesion(par)
    navigate(tomarDestino(), { replace: true })
  }

  return (
    <AuthCard
      title="Activa la verificación en dos pasos"
      subtitle="Para proteger los datos de tus contactos, todas las cuentas usan un código adicional al iniciar sesión."
      width={420}
    >
      <MfaEnrolamiento tokenDesafio={desafio.token} onActivado={alActivar} />
      <div style={{ textAlign: 'center', marginTop: 18 }}>
        <LinkButton onClick={() => { cancelarDesafio(); navigate('/login') }}>Cancelar</LinkButton>
      </div>
    </AuthCard>
  )
}
