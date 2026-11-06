import { sileo } from 'sileo'

// Confirmacion con el aviso flotante, igual que en el proyecto base.
export const confirmar = ({ titulo, descripcion = 'Esta acción no se puede deshacer', etiqueta = 'Eliminar', alConfirmar }) =>
  sileo({ title: titulo, description: descripcion, action: { label: etiqueta, onClick: alConfirmar } })
