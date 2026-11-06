import { useEffect, useRef, useState } from 'react'
import { CodigoField } from './FormField'
import AlertBox from './AlertBox'
import PrimaryButton from './PrimaryButton'
import { activarMfa, confirmarMfa } from '../../api/identidad'

// Muestra el QR del autenticador y confirma el primer codigo.
// Con tokenDesafio funciona sin sesion (enrolamiento obligatorio del login).
export default function MfaEnrolamiento({ tokenDesafio, onActivado }) {
  const [datos, setDatos] = useState(null)
  const [codigo, setCodigo] = useState('')
  const [error, setError] = useState('')
  const [cargando, setCargando] = useState(false)
  const pedido = useRef(false)

  // Cada llamada genera una clave nueva: el ref evita pedirla dos veces en desarrollo.
  useEffect(() => {
    if (pedido.current) return
    pedido.current = true
    activarMfa(tokenDesafio)
      .then(setDatos)
      .catch(err => setError(err.mensajeUsuario))
  }, [tokenDesafio])

  const confirmar = async e => {
    e.preventDefault()
    setError('')
    setCargando(true)
    try {
      await onActivado(await confirmarMfa(codigo, tokenDesafio))
    } catch (err) {
      setError(err.mensajeUsuario)
      setCodigo('')
      setCargando(false)
    }
  }

  if (!datos) {
    return error
      ? <AlertBox>{error}</AlertBox>
      : <p className="texto-suave" style={{ textAlign: 'center' }}>Generando código QR...</p>
  }

  return (
    <form onSubmit={confirmar}>
      <ol className="texto-suave" style={{ paddingLeft: 18, marginBottom: 14, lineHeight: 1.6 }}>
        <li>Instala Google Authenticator o Microsoft Authenticator.</li>
        <li>Escanea este código QR desde la aplicación.</li>
        <li>Escribe el código de 6 dígitos que aparece.</li>
      </ol>
      <img src={datos.qr} alt="Código QR para el autenticador" width={200} height={200}
        style={{ display: 'block', margin: '0 auto 12px', border: '1px solid #e5e7eb', borderRadius: 8 }} />
      <p className="texto-suave" style={{ fontSize: '0.78rem', textAlign: 'center', marginBottom: 16 }}>
        ¿No puedes escanear? Ingresa esta clave manualmente:
        <br />
        <code style={{ fontSize: '0.85rem', color: '#1a1a2e', wordBreak: 'break-all' }}>{datos.clave_manual}</code>
      </p>
      <CodigoField label="Código del autenticador" value={codigo} onChange={setCodigo} />
      <AlertBox>{error}</AlertBox>
      <PrimaryButton loading={cargando} disabled={codigo.length !== 6}>
        {cargando ? 'Confirmando...' : 'Confirmar y activar'}
      </PrimaryButton>
    </form>
  )
}
