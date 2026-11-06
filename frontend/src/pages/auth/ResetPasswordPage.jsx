import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { claseEnlace } from '../../components/ui/clases'
import AuthCard from '../../components/auth/AuthCard'
import FormField from '../../components/auth/FormField'
import AlertBox from '../../components/auth/AlertBox'
import PrimaryButton from '../../components/auth/PrimaryButton'
import { restablecer } from '../../api/identidad'

// Destino del enlace del correo de recuperacion: /reset-password?token=...&email=...
export default function ResetPasswordPage() {
  const [params] = useSearchParams()
  const token = params.get('token') || ''
  const correo = params.get('email') || ''
  const [contrasena, setContrasena] = useState('')
  const [confirmacion, setConfirmacion] = useState('')
  const [error, setError] = useState(token ? '' : 'El enlace de recuperación no es válido.')
  const [listo, setListo] = useState(false)
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
      await restablecer(token, contrasena)
      setListo(true)
    } catch (err) {
      setError(err.mensajeUsuario)
    } finally {
      setCargando(false)
    }
  }

  return (
    <AuthCard title="Restablecer contraseña" subtitle={correo}>
      {listo ? (
        <AlertBox type="success">Contraseña actualizada. Ya puedes iniciar sesión con tu nueva contraseña.</AlertBox>
      ) : token ? (
        <form onSubmit={enviar}>
          <FormField label="Nueva contraseña (mínimo 8 caracteres)" type="password" value={contrasena} onChange={setContrasena} autoComplete="new-password" autoFocus />
          <FormField label="Confirmar contraseña" type="password" value={confirmacion} onChange={setConfirmacion} autoComplete="new-password" />
          <AlertBox>{error}</AlertBox>
          <PrimaryButton loading={cargando}>{cargando ? 'Guardando...' : 'Cambiar contraseña'}</PrimaryButton>
        </form>
      ) : (
        <AlertBox>{error}</AlertBox>
      )}
      <div className="mt-[18px] text-center">
        <Link className={claseEnlace} to="/login" state={{ correo }}>Ir a iniciar sesión</Link>
      </div>
    </AuthCard>
  )
}
