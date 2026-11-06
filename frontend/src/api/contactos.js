// Endpoints de contactos y etiquetas.
import { del, get, patch, post } from './cliente'

export const POR_PAGINA = 50

export const listarContactos = ({ texto, etiqueta, cursor } = {}) =>
  get('contactos', { texto, etiqueta, cursor, limite: POR_PAGINA })
export const etiquetas = () => get('contactos/etiquetas')
export const crearContacto = ({ telefono, nombre, etiquetas: lista }) =>
  post('contactos', { telefono, nombre, etiquetas: lista })
export const editarContacto = (id, cambios) => patch(`contactos/${id}`, cambios)
export const eliminarContacto = id => del(`contactos/${id}`)
export const eliminarContactos = ids => post('contactos/eliminar-lote', { ids })

// El backend lee el CSV por encabezado: telefono, nombre, etiquetas y notas.
export const importarCsv = (archivo, { separador = ',', encabezado = true } = {}) => {
  const datos = new FormData()
  datos.append('archivo', archivo)
  datos.append('separador', separador)
  datos.append('encabezado', encabezado ? 'true' : 'false')
  return post('contactos/importar', datos)
}
