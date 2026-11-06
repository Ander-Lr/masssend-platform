import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { sileo } from 'sileo'
import FormField from '../components/auth/FormField'
import AlertBox from '../components/auth/AlertBox'
import LinkButton from '../components/auth/LinkButton'
import MfaEnrolamiento from '../components/auth/MfaEnrolamiento'
import Boton from '../components/ui/Boton'
import Insignia from '../components/ui/Insignia'
import Pagina from '../components/ui/Pagina'
import Tarjeta from '../components/ui/Tarjeta'
import { cambiarContrasena, desactivarMfa } from '../api/identidad'
import { useAuth } from '../context/AuthContext'

function DobleFactor() {
  const { usuario, recargarPerfil } = useAuth()
  const [desactivando, setDesactivando] = useState(false)
  const [activando, setActivando] = useState(false)
  const [contrasena, setContrasena] = useState('')
  const [error, setError] = useState('')
  const [cargando, setCargando] = useState(false)

  const desactivar = async e => {
    e.preventDefault()
    setError('')
    setCargando(true)
    try {
      await desactivarMfa(contrasena)
      await recargarPerfil()
      setDesactivando(false)
      setContrasena('')
      sileo.success({ title: 'Doble factor desactivado' })
    } catch (err) {
      setError(err.mensajeUsuario)
    } finally {
      setCargando(false)
    }
  }

  const alActivar = async () => {
    await recargarPerfil()
    setActivando(false)
    sileo.success({ title: 'Doble factor activado' })
  }

  return (
    <Tarjeta>
      <div className="mb-2.5 flex items-center justify-between gap-3">
        <h2 className="text-base font-bold">Verificación en dos pasos</h2>
        <Insignia color={usuario.mfa_activo ? 'verde' : 'roja'}>{usuario.mfa_activo ? 'Activa' : 'Inactiva'}</Insignia>
      </div>

      {usuario.mfa_activo && !desactivando && (
        <>
          <p className="mb-3.5 text-[0.88rem] leading-normal text-gray-500">
            Cada inicio de sesión pide el código de tu aplicación de autenticación además de la contraseña.
          </p>
          <LinkButton peligro onClick={() => { setDesactivando(true); setError('') }}>
            Desactivar verificación en dos pasos
          </LinkButton>
        </>
      )}

      {usuario.mfa_activo && desactivando && (
        <form onSubmit={desactivar}>
          <AlertBox type="info">
            El doble factor es obligatorio. Si lo desactivas, el próximo inicio de sesión te pedirá configurarlo otra vez.
          </AlertBox>
          <FormField label="Confirma tu contraseña" type="password" value={contrasena} onChange={setContrasena} autoComplete="current-password" autoFocus />
          <AlertBox>{error}</AlertBox>
          <div className="flex gap-2.5">
            <Boton type="submit" variante="peligro" disabled={cargando}>{cargando ? 'Desactivando...' : 'Confirmar desactivación'}</Boton>
            <Boton variante="secundario" onClick={() => { setDesactivando(false); setContrasena('') }}>Cancelar</Boton>
          </div>
        </form>
      )}

      {!usuario.mfa_activo && !activando && (
        <>
          <p className="mb-3.5 text-[0.88rem] leading-normal text-gray-500">
            Protege tu cuenta con un código adicional generado por Google Authenticator o Microsoft Authenticator.
          </p>
          <Boton onClick={() => setActivando(true)}>Activar verificación en dos pasos</Boton>
        </>
      )}

      {!usuario.mfa_activo && activando && <MfaEnrolamiento onActivado={alActivar} />}
    </Tarjeta>
  )
}

function CambioContrasena() {
  const { cerrarSesion } = useAuth()
  const navigate = useNavigate()
  const [actual, setActual] = useState('')
  const [nueva, setNueva] = useState('')
  const [confirmacion, setConfirmacion] = useState('')
  const [error, setError] = useState('')
  const [cargando, setCargando] = useState(false)

  // El backend revoca todas las sesiones al cambiar la contrasena: se vuelve a entrar.
  const enviar = async e => {
    e.preventDefault()
    setError('')
    if (nueva !== confirmacion) {
      setError('Las contraseñas nuevas no coinciden.')
      return
    }
    setCargando(true)
    try {
      await cambiarContrasena(actual, nueva)
      await cerrarSesion()
      navigate('/login', { state: { aviso: 'Contraseña actualizada. Inicia sesión con tu nueva contraseña.' } })
    } catch (err) {
      setError(err.mensajeUsuario)
      setCargando(false)
    }
  }

  return (
    <Tarjeta titulo="Cambiar contraseña">
      <p className="mb-4 text-[0.88rem] text-gray-500">Al cambiarla se cierran las sesiones abiertas en todos tus dispositivos.</p>
      <form onSubmit={enviar}>
        <FormField label="Contraseña actual" type="password" value={actual} onChange={setActual} autoComplete="current-password" />
        <FormField label="Nueva contraseña (mínimo 8 caracteres)" type="password" value={nueva} onChange={setNueva} autoComplete="new-password" />
        <FormField label="Confirmar nueva contraseña" type="password" value={confirmacion} onChange={setConfirmacion} autoComplete="new-password" />
        <AlertBox>{error}</AlertBox>
        <Boton type="submit" disabled={cargando}>{cargando ? 'Guardando...' : 'Cambiar contraseña'}</Boton>
      </form>
    </Tarjeta>
  )
}

export default function SeguridadPage() {
  const { usuario } = useAuth()
  return (
    <Pagina titulo="Seguridad de la cuenta" subtitulo={<>Cuenta: <strong>{usuario.correo}</strong></>} fondo="bg-lienzo">
      <div className="grid max-w-[960px] grid-cols-[repeat(auto-fit,minmax(280px,1fr))] items-start gap-4">
        <DobleFactor />
        <CambioContrasena />
      </div>
    </Pagina>
  )
}
