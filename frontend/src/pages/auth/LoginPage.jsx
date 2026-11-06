import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import AuthCard from '../../components/auth/AuthCard'
import FormField from '../../components/auth/FormField'
import AlertBox from '../../components/auth/AlertBox'
import PrimaryButton from '../../components/auth/PrimaryButton'
import GoogleButton from '../../components/auth/GoogleButton'
import { useAuth } from '../../context/AuthContext'
import { rutaDelPaso } from './pasos'

export default function LoginPage() {
  const { iniciarSesion } = useAuth()
  const navigate = useNavigate()
  const { state } = useLocation()
  const [correo, setCorreo] = useState(state?.correo || '')
  const [contrasena, setContrasena] = useState('')
  const [error, setError] = useState('')
  const [cargando, setCargando] = useState(false)

  const enviar = async e => {
    e.preventDefault()
    setError('')
    setCargando(true)
    try {
      const paso = await iniciarSesion(correo.trim(), contrasena)
      navigate(rutaDelPaso(paso))
    } catch (err) {
      setError(err.mensajeUsuario)
      setCargando(false)
    }
  }

  return (
    <AuthCard subtitle="Sistema de Mensajería WhatsApp">
      <AlertBox type="success">{state?.aviso}</AlertBox>
      <form onSubmit={enviar}>
        <FormField label="Correo electrónico" type="email" value={correo} onChange={setCorreo} autoComplete="username" autoFocus />
        <FormField label="Contraseña" type="password" value={contrasena} onChange={setContrasena} autoComplete="current-password" />
        <AlertBox>{error}</AlertBox>
        <PrimaryButton loading={cargando}>{cargando ? 'Iniciando sesión...' : 'Iniciar sesión'}</PrimaryButton>
      </form>

      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 14, fontSize: '0.78rem' }}>
        <Link className="boton-enlace" to="/recuperar">¿Olvidaste tu contraseña?</Link>
        <Link className="boton-enlace" to="/registro">Crear cuenta nueva</Link>
      </div>

      <div className="separador">o</div>
      <GoogleButton onError={setError} />
    </AuthCard>
  )
}
