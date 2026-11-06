// Entradas de formulario con el borde verde al enfocar, como en el base.
export const claseEntrada =
  'w-full rounded-lg border-[1.5px] border-gray-200 bg-white px-3.5 py-2.5 text-[0.9rem] outline-none transition-colors focus:border-marca disabled:bg-gray-50'
export const claseFiltro =
  'rounded-lg border border-gray-200 bg-white px-3 py-2 text-[0.85rem] outline-none focus:border-marca'
export const claseCasilla = 'size-[15px] cursor-pointer accent-indigo-500'

export function Etiqueta({ children, className = '' }) {
  return <label className={`mb-1.5 block text-[0.82rem] font-semibold text-gray-700 ${className}`}>{children}</label>
}

export function Ayuda({ children, color = 'text-gray-500' }) {
  return <p className={`mt-1.5 text-[0.76rem] ${color}`}>{children}</p>
}
