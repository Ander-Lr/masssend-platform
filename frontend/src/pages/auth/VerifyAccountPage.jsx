import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { claseEnlace } from '../../components/ui/clases'
import AuthCard from '../../components/auth/AuthCard'
import FormField, { CodigoField } from '../../components/auth/FormField'
import AlertBox from '../../components/auth/AlertBox'
import PrimaryButton from '../../components/auth/PrimaryButton'
import LinkButton from '../../components/auth/LinkButton'
import { reenviarCodigo, verificar } from '../../api/identidad'

// El usuario escribe el codigo de 6 digitos que llego a su correo.
export default function VerifyAccountPage() {
  const navigate = useNavigate()
  const { state } = useLocation()
  const [correo, setCorreo] = useState(state?.correo || '')
  const [codigo, setCodigo] = useState('')
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  const [cargando, setCargando] = useState(false)
  const [reenviando, setReenviando] = useState(false)

  const enviar = async e => {
    e.preventDefault()
    setError('')
    setInfo('')
    setCargando(true)
    try {
      await verificar(correo.trim(), codigo)
      navigate('/login', { state: { correo, aviso: 'Tu cuenta quedó activa. Ya puedes iniciar sesión.' } })
    } catch (err) {
      setError(err.mensajeUsuario)
      setCargando(false)
    }
  }

  const reenviar = async () => {
    if (!correo) {
      setError('Escribe tu correo para reenviar el código.')
      return
    }
    setError('')
    setInfo('')
    setReenviando(true)
    try {
      await reenviarCodigo(correo.trim())
      setInfo('Si la cuenta está pendiente, te llegará un nuevo código.')
    } catch (err) {
      setError(err.mensajeUsuario)
    } finally {
      setReenviando(false)
    }
  }

  return (
    <AuthCard title="Verifica tu correo" subtitle="Ingresa el código de 6 dígitos que te enviamos">
      <form onSubmit={enviar}>
        <FormField label="Correo electrónico" type="email" value={correo} onChange={setCorreo} autoFocus={!correo} />
        <CodigoField label="Código de verificación" value={codigo} onChange={setCodigo} autoFocus={Boolean(correo)} />
        <AlertBox>{error}</AlertBox>
        <AlertBox type="success">{info}</AlertBox>
        <PrimaryButton loading={cargando} disabled={codigo.length !== 6}>
          {cargando ? 'Verificando...' : 'Activar cuenta'}
        </PrimaryButton>
      </form>
      <div className="mt-[18px] flex justify-between">
        <LinkButton onClick={reenviar}>{reenviando ? 'Enviando...' : 'Reenviar código'}</LinkButton>
        <Link className={claseEnlace} to="/login">Volver a iniciar sesión</Link>
      </div>
    </AuthCard>
  )
}
