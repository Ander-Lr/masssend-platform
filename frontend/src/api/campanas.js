// Endpoints de campanas, adjuntos y envio.
import { api, del, get, patch, post } from './cliente'

export const ESTADOS = {
  borrador: { label: 'Borrador', clase: 'gris' },
  en_curso: { label: 'En curso', clase: 'amarilla' },
  completada: { label: 'Completada', clase: 'verde' },
  cancelada: { label: 'Cancelada', clase: 'roja' },
}

export const listarCampanas = ({ estado, cursor, limite = 20 } = {}) => get('campanas', { estado, cursor, limite })
export const obtenerCampana = id => get(`campanas/${id}`)
export const crearCampana = ({ nombre, mensaje, etiquetas }) => post('campanas', { nombre, mensaje, etiquetas })
export const editarCampana = (id, cambios) => patch(`campanas/${id}`, cambios)
export const eliminarCampana = id => del(`campanas/${id}`)

export const subirAdjunto = (id, archivo) => {
  const datos = new FormData()
  datos.append('archivo', archivo)
  return post(`campanas/${id}/adjunto`, datos)
}
// El adjunto solo se descarga con el JWT del dueno: se recibe como Blob.
export const descargarAdjunto = id => api(`campanas/${id}/adjunto`)

export const lanzarCampana = id => post(`campanas/${id}/lanzar`)
export const cancelarCampana = id => post(`campanas/${id}/cancelar`)
export const progresoCampana = id => get(`campanas/${id}/progreso`)

// Mismos limites que el dominio: el tipo real lo comprueba el backend por su contenido.
export const ADJUNTOS = {
  'image/jpeg': 5, 'image/png': 5, 'image/webp': 5, 'video/mp4': 16,
}
export const ACEPTA_ADJUNTO = '.jpg,.jpeg,.png,.webp,.mp4'
export const MAX_MENSAJE = 4096

export function revisarAdjunto(archivo) {
  const limite = ADJUNTOS[archivo.type]
  if (!limite) return 'Formato no permitido. Usa JPG, PNG, WEBP o MP4.'
  if (archivo.size > limite * 1024 * 1024) return `El archivo supera ${limite} MB, el límite de WhatsApp para este formato.`
  return ''
}

// Igual que personalizar() del dominio: una variable desconocida queda tal cual.
export const personalizar = (plantilla, valores) =>
  plantilla.replace(/\{\{\s*(\w+)\s*\}\}/g, (texto, clave) => (valores[clave] ?? texto))
