import { sileo } from 'sileo'

// Confirmacion con el aviso flotante, igual que en el proyecto base.
// sileo es un objeto (sileo.action, sileo.error...), no una funcion, y su boton
// se declara como button: { title, onClick }.
export const confirmar = ({ titulo, descripcion = 'Esta acción no se puede deshacer', etiqueta = 'Eliminar', alConfirmar }) =>
  sileo.action({ title: titulo, description: descripcion, button: { title: etiqueta, onClick: alConfirmar } })
