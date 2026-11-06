import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { claseEnlace } from '../../components/ui/clases'
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

      <div className="mt-3.5 flex justify-between">
        <Link className={claseEnlace} to="/recuperar">¿Olvidaste tu contraseña?</Link>
        <Link className={claseEnlace} to="/registro">Crear cuenta nueva</Link>
      </div>

      <div className="my-5 flex items-center gap-2.5 text-[0.8rem] text-gray-400 before:h-px before:flex-1 before:bg-gray-200 after:h-px after:flex-1 after:bg-gray-200">o</div>
      <GoogleButton onError={setError} />
    </AuthCard>
  )
}
