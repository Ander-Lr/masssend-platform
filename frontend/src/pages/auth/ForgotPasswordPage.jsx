import { useState } from 'react'
import { Link } from 'react-router-dom'
import AuthCard from '../../components/auth/AuthCard'
import FormField from '../../components/auth/FormField'
import AlertBox from '../../components/auth/AlertBox'
import PrimaryButton from '../../components/auth/PrimaryButton'
import { solicitarRecuperacion } from '../../api/identidad'

export default function ForgotPasswordPage() {
  const [correo, setCorreo] = useState('')
  const [error, setError] = useState('')
  const [enviado, setEnviado] = useState(false)
  const [cargando, setCargando] = useState(false)

  const enviar = async e => {
    e.preventDefault()
    setError('')
    setCargando(true)
    try {
      await solicitarRecuperacion(correo.trim())
      setEnviado(true)
    } catch (err) {
      setError(err.mensajeUsuario)
    } finally {
      setCargando(false)
    }
  }

  return (
    <AuthCard title="Recuperar contraseña" subtitle="Te enviaremos un enlace a tu correo">
      {enviado ? (
        <AlertBox type="success">
          Si la cuenta existe, recibirás un correo con el enlace de recuperación. El enlace vence en 15 minutos.
        </AlertBox>
      ) : (
        <form onSubmit={enviar}>
          <FormField label="Correo electrónico" type="email" value={correo} onChange={setCorreo} autoFocus />
          <AlertBox>{error}</AlertBox>
          <PrimaryButton loading={cargando}>{cargando ? 'Enviando...' : 'Enviar enlace de recuperación'}</PrimaryButton>
        </form>
      )}
      <div style={{ textAlign: 'center', marginTop: 18 }}>
        <Link className="boton-enlace" to="/login">Volver a iniciar sesión</Link>
      </div>
    </AuthCard>
  )
}
