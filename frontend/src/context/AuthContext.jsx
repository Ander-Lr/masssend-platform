import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { tokens } from '../api/cliente'
import * as identidad from '../api/identidad'
import Boton from '../components/ui/Boton'
import { Fondo } from '../components/ui/Modal'

const AuthContext = createContext(null)
const CLAVE_DESAFIO = 'masssend.desafio'

// El desafio vive en sessionStorage: sobrevive a recargar la pagina del doble
// factor, pero se pierde al cerrar la pestana, igual que su vigencia corta.
const leerDesafio = () => {
  try {
    return JSON.parse(sessionStorage.getItem(CLAVE_DESAFIO)) || null
  } catch {
    return null
  }
}

export function AuthProvider({ children }) {
  // usuario: { id, nombre, correo, mfa_activo, es_staff } validado siempre por el backend
  const [usuario, setUsuario] = useState(null)
  // Sin token guardado no hay perfil que consultar: se arranca sin cargar.
  const [cargando, setCargando] = useState(() => Boolean(tokens.acceso()))
  const [desafio, setDesafioState] = useState(leerDesafio)
  const [sesionExpirada, setSesionExpirada] = useState(false)

  const cargarPerfil = useCallback(async () => {
    const datos = await identidad.perfil()
    setUsuario(datos)
    return datos
  }, [])

  useEffect(() => {
    if (!tokens.acceso()) return
    identidad.perfil()
      .then(setUsuario)
      .catch(() => tokens.borrar())
      .finally(() => setCargando(false))
  }, [])

  // El cliente HTTP avisa cuando ni la renovacion pudo salvar la sesion.
  useEffect(() => {
    const alExpirar = () => { if (usuario) setSesionExpirada(true) }
    window.addEventListener('sesion-expirada', alExpirar)
    return () => window.removeEventListener('sesion-expirada', alExpirar)
  }, [usuario])

  const setDesafio = useCallback(paso => {
    if (paso) sessionStorage.setItem(CLAVE_DESAFIO, JSON.stringify(paso))
    else sessionStorage.removeItem(CLAVE_DESAFIO)
    setDesafioState(paso)
  }, [])

  // Primer factor (contrasena o Google). Devuelve "totp" o "activar_mfa".
  const registrarPaso = useCallback((paso, correo = '') => {
    setDesafio({ siguiente: paso.siguiente, token: paso.token_desafio, expira: paso.expira_en, correo })
    return paso.siguiente
  }, [setDesafio])

  const iniciarSesion = useCallback(async (correo, contrasena) => {
    const paso = await identidad.iniciarSesion(correo, contrasena)
    return registrarPaso(paso, correo)
  }, [registrarPaso])

  // Cualquier camino que termine con tokens pasa por aqui.
  const completarSesion = useCallback(async par => {
    tokens.guardar(par)
    setDesafio(null)
    setSesionExpirada(false)
    return cargarPerfil()
  }, [cargarPerfil, setDesafio])

  const validarTotp = useCallback(async codigo => {
    const par = await identidad.validarTotp(desafio?.token, codigo)
    return completarSesion(par)
  }, [desafio, completarSesion])

  const cerrarSesion = useCallback(async () => {
    const renovacion = tokens.renovacion()
    if (renovacion) await identidad.cerrarSesion(renovacion).catch(() => {})
    tokens.borrar()
    setUsuario(null)
  }, [])

  const reingresar = () => {
    tokens.borrar()
    setSesionExpirada(false)
    setUsuario(null)
  }

  return (
    <AuthContext.Provider value={{
      usuario, cargando, desafio,
      iniciarSesion, registrarPaso, validarTotp, completarSesion, cerrarSesion,
      cancelarDesafio: () => setDesafio(null), recargarPerfil: cargarPerfil,
    }}>
      {children}
      {sesionExpirada && (
        <Fondo>
          <div className="w-full max-w-[380px] rounded-[14px] bg-white px-8 py-7 text-center shadow-2xl">
            <h3 className="mb-2 text-lg font-bold text-tinta">Tu sesión ha expirado</h3>
            <p className="mb-5 text-[0.9rem] leading-normal text-gray-500">
              Por seguridad, la sesión se cierra tras un tiempo de inactividad.
              Vuelve a iniciar sesión para continuar donde estabas.
            </p>
            <Boton bloque tamano="lg" onClick={reingresar}>Iniciar sesión de nuevo</Boton>
          </div>
        </Fondo>
      )}
    </AuthContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export const useAuth = () => useContext(AuthContext)
