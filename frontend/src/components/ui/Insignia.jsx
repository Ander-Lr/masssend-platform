const COLORES = {
  verde: 'bg-emerald-100 text-emerald-800',
  gris: 'bg-gray-100 text-gray-500',
  roja: 'bg-red-100 text-red-800',
  amarilla: 'bg-amber-100 text-amber-700',
  azul: 'bg-blue-100 text-blue-700',
  celeste: 'bg-sky-100 text-sky-700',
}

export default function Insignia({ color = 'gris', grande = false, className = '', children }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full font-bold ${grande ? 'px-4 py-1.5 text-[0.82rem]' : 'px-2.5 py-0.5 text-[0.72rem]'} ${COLORES[color]} ${className}`}>
      {children}
    </span>
  )
}

export function Punto({ encendido, parpadea = false }) {
  return (
    <span className={`size-2 shrink-0 rounded-full ${encendido ? 'bg-emerald-500 shadow-[0_0_6px_#10b981]' : 'bg-red-500'} ${!encendido && parpadea ? 'animate-pulse' : ''}`} />
  )
}
