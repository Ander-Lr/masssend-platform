// Menu lateral y accesos de Inicio. Cada fase agrega aqui sus modulos y en App.jsx sus rutas.
// soloStaff: el modulo solo aparece para cuentas staff; el backend igual lo valida.
export const MODULOS = [
  { id: 'inicio', ruta: '/', label: 'Inicio' },
  {
    id: 'campanas', ruta: '/campanas', label: 'Campañas',
    titulo: 'Campañas', desc: 'Crea mensajes personalizados y envíalos a tus contactos.', color: '#25d366',
  },
  {
    id: 'contactos', ruta: '/contactos', label: 'Contactos',
    titulo: 'Contactos', desc: 'Gestiona tu lista de clientes, etiquetas y bajas.', color: '#10b981',
  },
  {
    id: 'importar', ruta: '/importar', label: 'Importar CSV',
    titulo: 'Importar CSV', desc: 'Carga cientos de contactos desde un archivo.', color: '#7c3aed',
  },
  {
    id: 'mensajes', ruta: '/mensajes', label: 'Mensajes',
    titulo: 'Mensajes', desc: 'Historial de lo enviado y las respuestas de tus contactos.', color: '#3b82f6',
  },
  {
    id: 'reportes', ruta: '/reportes', label: 'Reportes',
    titulo: 'Reportes', desc: 'Entregas, lecturas y actividad de tus campañas.', color: '#6366f1',
  },
  {
    id: 'chat', ruta: '/chat', label: 'Chat', soloStaff: true,
    titulo: 'Chat', desc: 'Conversa con los contactos desde el número de la plataforma.', color: '#128c4a',
  },
  {
    id: 'whatsapp', ruta: '/whatsapp', label: 'Conectar WhatsApp', soloStaff: true,
    titulo: 'Conectar WhatsApp', desc: 'Vincula el número desde el que se envían las campañas.', color: '#25d366',
  },
  {
    id: 'creditos', ruta: '/creditos', label: 'Créditos',
    titulo: 'Créditos', desc: 'Consulta tu saldo y compra paquetes con PayPal o PayPhone.', color: '#f59e0b',
  },
  {
    id: 'asistente', ruta: '/asistente', label: 'Asistente IA',
    titulo: 'Asistente IA', desc: 'Resuelve dudas y redacta mensajes para tus campañas.', color: '#8b5cf6',
  },
  {
    id: 'seguridad', ruta: '/seguridad', label: 'Seguridad',
    titulo: 'Seguridad de la cuenta', desc: 'Doble factor y cambio de contraseña.', color: '#0ea5e9',
  },
]

export const modulosVisibles = usuario =>
  MODULOS.filter(m => !m.soloStaff || usuario?.es_staff)
