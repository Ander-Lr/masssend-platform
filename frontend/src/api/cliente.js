// Cliente HTTP unico de la API v1. Ninguna pantalla arma URLs ni encabezados:
// todas pasan por aqui. Agrega el JWT, renueva el token de acceso cuando vence
// y convierte las respuestas problem+json (RFC 9457) en un ErrorApi.

const BASE = '/api/v1'
const CLAVE_ACCESO = 'masssend.acceso'
const CLAVE_RENOVACION = 'masssend.renovacion'

export class ErrorApi extends Error {
  constructor(estado, cuerpo) {
    super(cuerpo?.detail || cuerpo?.title || 'No se pudo completar la solicitud.')
    this.estado = estado
    this.codigo = cuerpo?.codigo || ''
    this.campo = cuerpo?.campo || ''
    this.errores = cuerpo?.errores || []
    this.cuerpo = cuerpo
  }

  // Mensaje listo para mostrar: prioriza el detalle de cada campo invalido.
  get mensajeUsuario() {
    if (this.errores.length) {
      return this.errores.map(e => (e.campo ? `${e.campo}: ${e.detalle}` : e.detalle)).join(' ')
    }
    return this.message
  }
}

export const tokens = {
  acceso: () => localStorage.getItem(CLAVE_ACCESO),
  renovacion: () => localStorage.getItem(CLAVE_RENOVACION),
  guardar({ acceso, renovacion }) {
    localStorage.setItem(CLAVE_ACCESO, acceso)
    localStorage.setItem(CLAVE_RENOVACION, renovacion)
  },
  borrar() {
    localStorage.removeItem(CLAVE_ACCESO)
    localStorage.removeItem(CLAVE_RENOVACION)
  },
}

// Varias peticiones pueden vencer a la vez: todas esperan la misma renovacion.
let renovando = null

async function renovarAcceso() {
  const renovacion = tokens.renovacion()
  if (!renovacion) return false
  if (!renovando) {
    renovando = fetch(`${BASE}/auth/token/renovar`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ renovacion }),
    })
      .then(async r => {
        if (!r.ok) return false
        tokens.guardar(await r.json())
        return true
      })
      .catch(() => false)
      .finally(() => { renovando = null })
  }
  return renovando
}

async function leerCuerpo(respuesta) {
  if (respuesta.status === 204) return null
  const tipo = respuesta.headers.get('Content-Type') || ''
  if (tipo.includes('json')) return respuesta.json()
  if (tipo.startsWith('text/')) return respuesta.text()
  return respuesta.blob()
}

function construirUrl(ruta, consulta) {
  const url = `${BASE}/${ruta.replace(/^\//, '')}`
  if (!consulta) return url
  const params = new URLSearchParams()
  Object.entries(consulta).forEach(([clave, valor]) => {
    if (valor !== undefined && valor !== null && valor !== '') params.append(clave, valor)
  })
  const texto = params.toString()
  return texto ? `${url}?${texto}` : url
}

/**
 * Hace una peticion a la API v1.
 * @param {string} ruta    ruta relativa a /api/v1, por ejemplo "auth/yo"
 * @param {object} opciones metodo, cuerpo (objeto o FormData), consulta, publica
 */
export async function api(ruta, { metodo = 'GET', cuerpo, consulta, publica = false } = {}, reintento = true) {
  const encabezados = { Accept: 'application/json, application/problem+json' }
  const acceso = tokens.acceso()
  if (acceso && !publica) encabezados.Authorization = `Bearer ${acceso}`

  let body
  if (cuerpo instanceof FormData) {
    body = cuerpo
  } else if (cuerpo !== undefined) {
    encabezados['Content-Type'] = 'application/json'
    body = JSON.stringify(cuerpo)
  }

  let respuesta
  try {
    respuesta = await fetch(construirUrl(ruta, consulta), { method: metodo, headers: encabezados, body })
  } catch {
    throw new ErrorApi(0, { detail: 'No hay conexión con el servidor.' })
  }

  if (respuesta.status === 401 && !publica && acceso) {
    if (reintento && (await renovarAcceso())) {
      return api(ruta, { metodo, cuerpo, consulta, publica }, false)
    }
    tokens.borrar()
    window.dispatchEvent(new CustomEvent('sesion-expirada'))
  }

  const datos = await leerCuerpo(respuesta)
  if (!respuesta.ok) throw new ErrorApi(respuesta.status, typeof datos === 'object' ? datos : { detail: datos })
  return datos
}

export const get = (ruta, consulta, extra) => api(ruta, { ...extra, consulta })
export const post = (ruta, cuerpo, extra) => api(ruta, { ...extra, metodo: 'POST', cuerpo })
export const patch = (ruta, cuerpo, extra) => api(ruta, { ...extra, metodo: 'PATCH', cuerpo })
export const put = (ruta, cuerpo, extra) => api(ruta, { ...extra, metodo: 'PUT', cuerpo })
export const del = (ruta, extra) => api(ruta, { ...extra, metodo: 'DELETE' })
