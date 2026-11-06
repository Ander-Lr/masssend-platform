// Pantalla que corresponde a cada "siguiente" paso que devuelve el backend.
const RUTAS = { totp: '/doble-factor', activar_mfa: '/activar-doble-factor' }

export const rutaDelPaso = paso => RUTAS[paso] || '/login'
