// Vista previa de las reglas del objeto de valor Telefono del backend.
// Solo orienta al usuario: la validacion que cuenta es la del servidor.
export function revisarTelefono(crudo) {
  const texto = String(crudo || '').trim()
  if (!texto) return { ok: false, error: 'Teléfono vacío' }
  if (/[Ee][+-]?\d/.test(texto)) return { ok: false, error: 'Número en notación científica' }
  let limpio = texto.replace(/[^\d+]/g, '').replace(/^\+/, '')
  if (!/^\d+$/.test(limpio)) return { ok: false, error: 'Caracteres inválidos' }
  if (/^0\d{7,9}$/.test(limpio)) {
    if (limpio[1] !== '9') return { ok: false, error: 'Número fijo, no recibe WhatsApp' }
    limpio = `593${limpio.slice(1)}`
  }
  if (limpio.startsWith('593')) {
    if (!limpio.startsWith('5939')) return { ok: false, error: 'Número fijo de Ecuador' }
    if (limpio.length !== 12) return { ok: false, error: `Móvil de Ecuador con ${limpio.length} dígitos` }
    return { ok: true, numero: limpio }
  }
  if (limpio.length < 11) return { ok: false, error: `Muy corto (${limpio.length} dígitos)` }
  if (limpio.length > 15) return { ok: false, error: `Muy largo (${limpio.length} dígitos)` }
  return { ok: true, numero: limpio }
}

export const mostrarTelefono = numero => `+${numero}`
