// Lectura de CSV en el navegador para la vista previa y la asignacion de columnas.

export const SEPARADORES = [
  { valor: ',', label: 'Coma ( , ), estándar' },
  { valor: ';', label: 'Punto y coma ( ; )' },
  { valor: 'tab', label: 'Tabulación' },
  { valor: '|', label: 'Barra vertical ( | )' },
]
const CARACTER = { ',': ',', ';': ';', tab: '\t', '|': '|' }

export const CAMPOS = [
  { valor: '', label: 'No importar' },
  { valor: 'telefono', label: 'Teléfono (requerido)' },
  { valor: 'nombre', label: 'Nombre' },
  { valor: 'etiquetas', label: 'Etiquetas' },
  { valor: 'notas', label: 'Notas' },
]

// Respeta comillas, comillas dobles escapadas y saltos de linea dentro de un campo.
export function leerCsv(texto, separador) {
  const sep = CARACTER[separador] || ','
  const filas = []
  let fila = []
  let celda = ''
  let comillas = false
  const contenido = texto.replace(/^\uFEFF/, '')
  for (let i = 0; i < contenido.length; i++) {
    const c = contenido[i]
    if (comillas) {
      if (c === '"' && contenido[i + 1] === '"') { celda += '"'; i++ }
      else if (c === '"') comillas = false
      else celda += c
    } else if (c === '"') {
      comillas = true
    } else if (c === sep) {
      fila.push(celda.trim()); celda = ''
    } else if (c === '\n' || c === '\r') {
      if (c === '\r' && contenido[i + 1] === '\n') i++
      fila.push(celda.trim()); celda = ''
      filas.push(fila); fila = []
    } else {
      celda += c
    }
  }
  if (celda || fila.length) { fila.push(celda.trim()); filas.push(fila) }
  return filas.filter(f => f.some(v => v))
}

const ALIAS = {
  telefono: ['telefono', 'phone', 'tel', 'celular', 'movil', 'mobile', 'numero', 'whatsapp'],
  nombre: ['nombre', 'name', 'fullname', 'cliente'],
  etiquetas: ['etiqueta', 'tag', 'label', 'categoria', 'grupo'],
  notas: ['nota', 'note', 'obs', 'comentario', 'comment'],
}

const normalizar = texto => texto.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9]/g, '')

// Asigna cada columna a un campo segun su encabezado. Cada campo se usa una sola vez.
export function asignarColumnas(encabezados) {
  const asignadas = {}
  const usados = new Set()
  encabezados.forEach((encabezado, i) => {
    const n = normalizar(encabezado)
    const campo = Object.keys(ALIAS).find(c => !usados.has(c) && ALIAS[c].some(a => n.includes(a)))
    asignadas[i] = campo || ''
    if (campo) usados.add(campo)
  })
  return asignadas
}

// Sin encabezado se asume el orden telefono, nombre, etiquetas, notas.
export const asignacionPosicional = columnas =>
  Object.fromEntries(Array.from({ length: columnas }, (_, i) => [i, ['telefono', 'nombre', 'etiquetas', 'notas'][i] || '']))

const escapar = valor => (/[",\n\r]/.test(valor) ? `"${valor.replace(/"/g, '""')}"` : valor)

// Arma el CSV que se envia al backend con las columnas ya asignadas.
export function construirCsv(filas) {
  const lineas = ['telefono,nombre,etiquetas,notas']
  filas.forEach(f => lineas.push([f.telefono, f.nombre, f.etiquetas, f.notas].map(v => escapar(v || '')).join(',')))
  return new Blob([lineas.join('\n')], { type: 'text/csv' })
}

export function descargarPlantilla() {
  const contenido = 'telefono,nombre,etiquetas,notas\n0991234567,Juan Pérez,cliente,Interesado\n593987654321,María López,"lead,vip",\n'
  const url = URL.createObjectURL(new Blob([`\uFEFF${contenido}`], { type: 'text/csv' }))
  const enlace = document.createElement('a')
  enlace.href = url
  enlace.download = 'plantilla_contactos.csv'
  enlace.click()
  URL.revokeObjectURL(url)
}
