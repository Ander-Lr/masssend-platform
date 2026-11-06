// Endpoints del asistente de IA local.
import { get, post } from './cliente'

export const estadoAsistente = () => get('asistente/salud')
export const preguntar = (pregunta, historial) => post('asistente/mensajes', { pregunta, historial })
