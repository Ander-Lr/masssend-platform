import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { sileo } from 'sileo'
import FormField from '../components/auth/FormField'
import AlertBox from '../components/auth/AlertBox'
import LinkButton from '../components/auth/LinkButton'
import MfaEnrolamiento from '../components/auth/MfaEnrolamiento'
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
    <div className="tarjeta">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, marginBottom: 10 }}>
        <h2 className="tarjeta-titulo" style={{ margin: 0 }}>Verificación en dos pasos</h2>
        <span className={`insignia ${usuario.mfa_activo ? 'insignia-verde' : 'insignia-roja'}`}>
          {usuario.mfa_activo ? 'Activa' : 'Inactiva'}
        </span>
      </div>

      {usuario.mfa_activo && !desactivando && (
        <>
          <p className="texto-suave" style={{ marginBottom: 14, lineHeight: 1.5 }}>
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
          <div style={{ display: 'flex', gap: 10 }}>
            <button type="submit" className="boton boton-peligro" disabled={cargando}>
              {cargando ? 'Desactivando...' : 'Confirmar desactivación'}
            </button>
            <button type="button" className="boton boton-secundario" onClick={() => { setDesactivando(false); setContrasena('') }}>
              Cancelar
            </button>
          </div>
        </form>
      )}

      {!usuario.mfa_activo && !activando && (
        <>
          <p className="texto-suave" style={{ marginBottom: 14, lineHeight: 1.5 }}>
            Protege tu cuenta con un código adicional generado por Google Authenticator o Microsoft Authenticator.
          </p>
          <button className="boton boton-primario" onClick={() => setActivando(true)}>
            Activar verificación en dos pasos
          </button>
        </>
      )}

      {!usuario.mfa_activo && activando && <MfaEnrolamiento onActivado={alActivar} />}
    </div>
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
    <div className="tarjeta">
      <h2 className="tarjeta-titulo">Cambiar contraseña</h2>
      <p className="texto-suave" style={{ marginBottom: 16 }}>Al cambiarla se cierran las sesiones abiertas en todos tus dispositivos.</p>
      <form onSubmit={enviar}>
        <FormField label="Contraseña actual" type="password" value={actual} onChange={setActual} autoComplete="current-password" />
        <FormField label="Nueva contraseña (mínimo 8 caracteres)" type="password" value={nueva} onChange={setNueva} autoComplete="new-password" />
        <FormField label="Confirmar nueva contraseña" type="password" value={confirmacion} onChange={setConfirmacion} autoComplete="new-password" />
        <AlertBox>{error}</AlertBox>
        <button type="submit" className="boton boton-primario" disabled={cargando}>
          {cargando ? 'Guardando...' : 'Cambiar contraseña'}
        </button>
      </form>
    </div>
  )
}

export default function SeguridadPage() {
  const { usuario } = useAuth()
  return (
    <div className="pagina">
      <div className="pagina-encabezado">
        <div>
          <h1 className="pagina-titulo">Seguridad de la cuenta</h1>
          <p className="pagina-subtitulo">Cuenta: <strong>{usuario.correo}</strong></p>
        </div>
      </div>
      <div className="rejilla" style={{ maxWidth: 960, alignItems: 'start' }}>
        <DobleFactor />
        <CambioContrasena />
      </div>
    </div>
  )
}
