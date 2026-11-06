import { Navigate, Route, Routes } from 'react-router-dom'
import { Toaster } from 'sileo'
import { AuthProvider, useAuth } from './context/AuthContext'
import Layout from './components/layout/Layout'
import LoginPage from './pages/auth/LoginPage'
import RegisterPage from './pages/auth/RegisterPage'
import VerifyAccountPage from './pages/auth/VerifyAccountPage'
import ForgotPasswordPage from './pages/auth/ForgotPasswordPage'
import ResetPasswordPage from './pages/auth/ResetPasswordPage'
import TotpPage from './pages/auth/TotpPage'
import EnrolarMfaPage from './pages/auth/EnrolarMfaPage'
import GoogleCallbackPage from './pages/auth/GoogleCallbackPage'
import InicioPage from './pages/InicioPage'
import SeguridadPage from './pages/SeguridadPage'

function Cargando() {
  return <div className="loading" style={{ height: '100vh' }}>Cargando...</div>
}

// Solo con sesion. Sin ella, vuelve al login.
function Privada({ children }) {
  const { usuario, cargando } = useAuth()
  if (cargando) return <Cargando />
  return usuario ? children : <Navigate to="/login" replace />
}

// Solo sin sesion. Con ella, va al inicio.
function Publica({ children }) {
  const { usuario, cargando } = useAuth()
  if (cargando) return <Cargando />
  return usuario ? <Navigate to="/" replace /> : children
}

// Solo para cuentas staff; el backend igual responde 403 a las demas.
// eslint-disable-next-line no-unused-vars
function SoloStaff({ children }) {
  const { usuario } = useAuth()
  return usuario?.es_staff ? children : <Navigate to="/" replace />
}

function Rutas() {
  return (
    <Routes>
      <Route path="/login" element={<Publica><LoginPage /></Publica>} />
      <Route path="/registro" element={<Publica><RegisterPage /></Publica>} />
      <Route path="/verificar" element={<Publica><VerifyAccountPage /></Publica>} />
      <Route path="/recuperar" element={<Publica><ForgotPasswordPage /></Publica>} />
      <Route path="/doble-factor" element={<Publica><TotpPage /></Publica>} />
      <Route path="/activar-doble-factor" element={<Publica><EnrolarMfaPage /></Publica>} />
      <Route path="/auth/google/callback" element={<Publica><GoogleCallbackPage /></Publica>} />
      {/* El enlace del correo de recuperacion se abre con o sin sesion. */}
      <Route path="/reset-password" element={<ResetPasswordPage />} />

      <Route element={<Privada><Layout /></Privada>}>
        <Route index element={<InicioPage />} />
        <Route path="seguridad" element={<SeguridadPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <Rutas />
      <Toaster position="bottom-center" />
    </AuthProvider>
  )
}
