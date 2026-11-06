// Notificaciones por correo y cola de correos. Solo staff.
import { get, post } from './cliente'

export const enviarNotificacion = ({ destinatario, asunto, titulo, mensaje, firma, archivo }) => {
  if (!archivo) return post('notificaciones', { destinatario, asunto, titulo, mensaje, firma })
  const datos = new FormData()
  Object.entries({ destinatario, asunto, titulo, mensaje, firma }).forEach(([k, v]) => datos.append(k, v || ''))
  datos.append('archivo', archivo)
  return post('notificaciones', datos)
}

export const tareasCorreo = cursor => get('cola-correos/tareas', { cursor, limite: 50 })
export const pausarCola = () => post('cola-correos/pausar')
export const reanudarCola = () => post('cola-correos/reanudar')

export const TIPOS_CORREO = {
  ACCOUNT_VERIFICATION: 'Verificación de cuenta',
  RESEND_VERIFICATION_CODE: 'Reenvío de código',
  PASSWORD_RECOVERY: 'Recuperación de contraseña',
  CUSTOM_NOTIFICATION: 'Notificación',
  ATTACHMENT_NOTIFICATION: 'Notificación con adjunto',
}
export const ESTADOS_CORREO = {
  PENDING: { label: 'Pendiente', color: 'amarilla' },
  PROCESSING: { label: 'Procesando', color: 'azul' },
  SENT: { label: 'Enviado', color: 'verde' },
  FAILED: { label: 'Fallido', color: 'roja' },
}

// Mismos tipos que acepta el dominio; el contenido real lo revisa el backend.
export const ACEPTA_ADJUNTO_CORREO = '.pdf,.png,.jpg,.jpeg,.docx,.xlsx'
