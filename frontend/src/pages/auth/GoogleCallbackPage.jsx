import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { claseEnlace } from '../../components/ui/clases'
import AuthCard from '../../components/auth/AuthCard'
import AlertBox from '../../components/auth/AlertBox'
import { completarGoogle } from '../../api/identidad'
import { useAuth } from '../../context/AuthContext'
import { rutaDelPaso } from './pasos'

// Google vuelve aqui con ?state=...&code=... y el backend responde el siguiente paso.
export default function GoogleCallbackPage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const { registrarPaso } = useAuth()
  const state = params.get('state')
  const code = params.get('code')
  const valido = Boolean(state && code && !params.get('error'))
  const [error, setError] = useState(valido ? '' : 'Google no completó el acceso. Intenta de nuevo.')
  const procesado = useRef(false)

  useEffect(() => {
    // El state es de un solo uso: se envia una vez aunque el efecto se repita.
    if (procesado.current) return
    procesado.current = true
    // El codigo de Google es de un solo uso: se quita de la barra de direcciones.
    window.history.replaceState(null, '', '/auth/google/callback')
    if (!valido) return
    completarGoogle(state, code)
      .then(paso => navigate(rutaDelPaso(registrarPaso(paso)), { replace: true }))
      .catch(err => setError(err.mensajeUsuario))
  }, [state, code, valido, navigate, registrarPaso])

  return (
    <AuthCard title="Acceso con Google">
      {error ? <AlertBox>{error}</AlertBox> : <p className="text-center text-[0.88rem] text-gray-500">Validando tu cuenta de Google...</p>}
      {error && (
        <div className="text-center">
          <Link className={claseEnlace} to="/login">Volver a iniciar sesión</Link>
        </div>
      )}
    </AuthCard>
  )
}
