// Endpoints de creditos y pagos.
import { get, post } from './cliente'

export const paquetes = () => get('creditos/paquetes')
export const saldo = () => get('creditos/saldo')
export const movimientos = cursor => get('creditos/movimientos', { cursor, limite: 20 })

// El precio lo fija el servidor: solo se envia el paquete y la pasarela.
export const iniciarCompra = (paqueteId, pasarela) =>
  post('pagos/checkout', { paquete_id: paqueteId, pasarela })
export const confirmarCompra = (compraId, datosPasarela = {}) =>
  post('pagos/confirmar', { compra_id: compraId, datos_pasarela: datosPasarela })

// La pasarela vuelve solo con su referencia: se recuerda que compra le corresponde.
const CLAVE_COMPRAS = 'masssend.compras'

const leerCompras = () => {
  try {
    return JSON.parse(localStorage.getItem(CLAVE_COMPRAS)) || {}
  } catch {
    return {}
  }
}

export const comprasPendientes = {
  guardar(compra) {
    const compras = leerCompras()
    compras[compra.referencia] = { id: compra.compra_id, pasarela: compra.pasarela, creditos: compra.creditos }
    try { localStorage.setItem(CLAVE_COMPRAS, JSON.stringify(compras)) } catch { /* sin almacenamiento */ }
  },
  buscar: referencia => leerCompras()[referencia] || null,
  quitar(referencia) {
    const compras = leerCompras()
    delete compras[referencia]
    try { localStorage.setItem(CLAVE_COMPRAS, JSON.stringify(compras)) } catch { /* sin almacenamiento */ }
  },
}
