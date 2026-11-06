// Menu lateral y accesos de Inicio. Cada fase agrega aqui sus modulos y en App.jsx sus rutas.
// soloStaff: el modulo solo aparece para cuentas staff; el backend igual lo valida.
export const MODULOS = [
  { id: 'inicio', ruta: '/', label: 'Inicio' },
  {
    id: 'seguridad', ruta: '/seguridad', label: 'Seguridad',
    titulo: 'Seguridad de la cuenta', desc: 'Doble factor y cambio de contraseña.', color: '#0ea5e9',
  },
]

export const modulosVisibles = usuario =>
  MODULOS.filter(m => !m.soloStaff || usuario?.es_staff)
