import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { Toaster } from 'sileo'
import { AuthProvider, useAuth } from './context/AuthContext'
import { WhatsappProvider } from './context/WhatsappContext'
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
import CreditosPage from './pages/CreditosPage'
import ContactosPage from './pages/ContactosPage'
import CampanasPage from './pages/CampanasPage'
import MensajesPage from './pages/MensajesPage'
import ReportesPage from './pages/ReportesPage'
import ChatPage from './pages/ChatPage'
import WhatsAppPage from './pages/WhatsAppPage'
import NotificacionesPage from './pages/NotificacionesPage'
import ColaCorreosPage from './pages/ColaCorreosPage'
import ImportarContactosPage from './pages/ImportarContactosPage'
import RetornoPagoPage from './pages/RetornoPagoPage'
import PagoLocalPage from './pages/PagoLocalPage'
import AsistentePage from './pages/AsistentePage'
import { recordarDestino } from './pages/auth/pasos'

function Cargando() {
  return <div className="flex h-screen items-center justify-center text-[0.9rem] text-gray-500">Cargando...</div>
}

// Solo con sesion. Sin ella, recuerda la pagina pedida y va al login.
function Privada({ children }) {
  const { usuario, cargando } = useAuth()
  const { pathname, search } = useLocation()
  if (cargando) return <Cargando />
  if (usuario) return children
  if (pathname !== '/') recordarDestino(pathname + search)
  return <Navigate to="/login" replace />
}

// Solo sin sesion. Con ella, va al inicio.
function Publica({ children }) {
  const { usuario, cargando } = useAuth()
  if (cargando) return <Cargando />
  return usuario ? <Navigate to="/" replace /> : children
}

// Solo para cuentas staff; el backend igual responde 403 a las demas.
function SoloStaff({ children }) {
  const { usuario } = useAuth()
  return usuario?.es_staff ? children : <Navigate to="/" replace />
}

function Rutas() {
  // Postman abre /?pagar=<url_pago> para entrar a PayPhone desde el dominio registrado.
  const { pathname, search } = useLocation()
  const pagar = pathname === '/' ? new URLSearchParams(search).get('pagar') : null
  if (pagar !== null) return <PagoLocalPage url={pagar} />

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
      {/* PayPal y PayPhone vuelven aqui despues del pago. */}
      <Route path="/billing/return" element={<RetornoPagoPage />} />

      <Route element={<Privada><WhatsappProvider><Layout /></WhatsappProvider></Privada>}>
        <Route index element={<InicioPage />} />
        <Route path="campanas" element={<CampanasPage />} />
        <Route path="contactos" element={<ContactosPage />} />
        <Route path="importar" element={<ImportarContactosPage />} />
        <Route path="mensajes" element={<MensajesPage />} />
        <Route path="reportes" element={<ReportesPage />} />
        <Route path="chat" element={<SoloStaff><ChatPage /></SoloStaff>} />
        <Route path="whatsapp" element={<SoloStaff><WhatsAppPage /></SoloStaff>} />
        <Route path="notificaciones" element={<SoloStaff><NotificacionesPage /></SoloStaff>} />
        <Route path="cola-correos" element={<SoloStaff><ColaCorreosPage /></SoloStaff>} />
        <Route path="creditos" element={<CreditosPage />} />
        <Route path="asistente" element={<AsistentePage />} />
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
