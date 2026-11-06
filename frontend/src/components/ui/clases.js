// Clases de botones reutilizables en enlaces y botones.
const VARIANTES = {
  primario: 'bg-marca text-white hover:bg-marca-oscuro',
  secundario: 'bg-gray-100 text-gray-700 border border-gray-200 font-semibold hover:bg-gray-200',
  peligro: 'bg-red-500 text-white hover:bg-red-600',
  indigo: 'bg-indigo-500 text-white hover:bg-indigo-600',
  violeta: 'bg-violet-600 text-white hover:bg-violet-700',
  contorno: 'bg-white text-violet-600 border-[1.5px] border-violet-600 font-semibold hover:bg-violet-50',
  blanco: 'bg-white text-gray-700 border-[1.5px] border-gray-200 font-semibold hover:border-marca',
  oscuro: 'bg-emerald-800 text-white font-semibold hover:bg-emerald-900',
}
const TAMANOS = {
  sm: 'px-3.5 py-1.5 text-[0.8rem]',
  md: 'px-[18px] py-2.5 text-[0.88rem]',
  lg: 'px-[22px] py-3 text-[0.9rem]',
}

export const claseBoton = ({ variante = 'primario', tamano = 'md', bloque = false } = {}) =>
  `inline-flex items-center justify-center gap-1.5 rounded-lg font-bold transition-colors no-underline
   disabled:bg-gray-400 disabled:border-gray-400 disabled:text-white
   ${VARIANTES[variante]} ${TAMANOS[tamano]} ${bloque ? 'w-full' : ''}`


export const claseEnlace = 'text-[0.82rem] font-semibold text-marca-enlace underline'
