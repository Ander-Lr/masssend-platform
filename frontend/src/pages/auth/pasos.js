// Pantalla que corresponde a cada "siguiente" paso que devuelve el backend.
const RUTAS = { totp: '/doble-factor', activar_mfa: '/activar-doble-factor' }

export const rutaDelPaso = paso => RUTAS[paso] || '/login'

// Pagina privada que se intento abrir sin sesion, por ejemplo el retorno de un pago.
const CLAVE_VOLVER = 'masssend.volverA'

export const recordarDestino = ruta => {
  try { sessionStorage.setItem(CLAVE_VOLVER, ruta) } catch { /* sin almacenamiento */ }
}

export const tomarDestino = () => {
  try {
    const ruta = sessionStorage.getItem(CLAVE_VOLVER)
    sessionStorage.removeItem(CLAVE_VOLVER)
    return ruta && ruta.startsWith('/') && !ruta.startsWith('//') ? ruta : '/'
  } catch {
    return '/'
  }
}
