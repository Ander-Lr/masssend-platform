// Endpoints de WhatsApp, mensajes, conversaciones y reportes.
import { get, post } from './cliente'

export const ESTADOS_ENTREGA = {
  pendiente: { label: 'Pendiente', color: 'amarilla' },
  enviado: { label: 'Enviado', color: 'gris' },
  entregado: { label: 'Entregado', color: 'azul' },
  leido: { label: 'Leído', color: 'verde' },
  fallido: { label: 'Fallido', color: 'roja' },
}

// Numero de WhatsApp de toda la plataforma: solo staff.
export const estadoWhatsapp = () => get('whatsapp/estado')
export const vincularWhatsapp = telefono => post('whatsapp/vinculacion', { telefono })
export const cerrarSesionWhatsapp = () => post('whatsapp/cerrar-sesion')

export const listarMensajes = ({ texto, direccion, estado, telefono, cursor, limite = 50 } = {}) =>
  get('mensajes', { texto, direccion, estado, telefono, cursor, limite })
export const eliminarMensajes = ids => post('mensajes/eliminar-lote', { ids })

export const listarConversaciones = cursor => get('conversaciones', { cursor, limite: 30 })
export const enviarMensajeChat = (telefono, texto) =>
  post(`conversaciones/${encodeURIComponent(telefono)}/mensajes`, { texto })

export const reporte = ({ desde, hasta } = {}) => get('reportes', { desde, hasta })

export const fechaHora = valor => new Date(valor).toLocaleString('es-EC', { dateStyle: 'short', timeStyle: 'short' })
