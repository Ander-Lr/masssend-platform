import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import AuthCard from '../../components/auth/AuthCard'
import FormField from '../../components/auth/FormField'
import AlertBox from '../../components/auth/AlertBox'
import PrimaryButton from '../../components/auth/PrimaryButton'
import { registrar } from '../../api/identidad'

// Crea la cuenta. Queda inactiva hasta verificar el codigo enviado por correo.
export default function RegisterPage() {
  const navigate = useNavigate()
  const [nombre, setNombre] = useState('')
  const [correo, setCorreo] = useState('')
  const [contrasena, setContrasena] = useState('')
  const [confirmacion, setConfirmacion] = useState('')
  const [error, setError] = useState('')
  const [cargando, setCargando] = useState(false)

  const enviar = async e => {
    e.preventDefault()
    setError('')
    if (contrasena !== confirmacion) {
      setError('Las contraseñas no coinciden.')
      return
    }
    setCargando(true)
    try {
      const creada = await registrar(nombre.trim(), correo.trim(), contrasena)
      navigate('/verificar', { state: { correo: creada.correo } })
    } catch (err) {
      setError(err.mensajeUsuario)
      setCargando(false)
    }
  }

  return (
    <AuthCard title="Crear cuenta" subtitle="Te enviaremos un código de verificación por correo">
      <form onSubmit={enviar}>
        <FormField label="Nombre completo" value={nombre} onChange={setNombre} autoComplete="name" autoFocus />
        <FormField label="Correo electrónico" type="email" value={correo} onChange={setCorreo} autoComplete="email" />
        <FormField label="Contraseña (mínimo 8 caracteres)" type="password" value={contrasena} onChange={setContrasena} autoComplete="new-password" />
        <FormField label="Confirmar contraseña" type="password" value={confirmacion} onChange={setConfirmacion} autoComplete="new-password" />
        <AlertBox>{error}</AlertBox>
        <PrimaryButton loading={cargando}>{cargando ? 'Creando cuenta...' : 'Registrarme'}</PrimaryButton>
      </form>
      <div style={{ textAlign: 'center', marginTop: 18 }}>
        <Link className="boton-enlace" to="/login">¿Ya tienes cuenta? Inicia sesión</Link>
      </div>
    </AuthCard>
  )
}
