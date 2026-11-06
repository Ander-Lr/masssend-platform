export default function Progreso({ porcentaje, activo = false, color }) {
  return (
    <div className="h-[7px] overflow-hidden rounded bg-gray-200">
      <div
        className={`h-full rounded transition-[width] duration-500 ${color ? '' : activo ? 'animate-pulse bg-gradient-to-r from-amber-500 to-amber-400' : 'bg-gradient-to-r from-emerald-500 to-emerald-400'}`}
        style={{ width: `${Math.min(porcentaje, 100)}%`, background: color }}
      />
    </div>
  )
}

export function Spinner({ tamano = 14 }) {
  return (
    <svg width={tamano} height={tamano} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" className="shrink-0 animate-spin" aria-hidden="true">
      <path d="M21 12a9 9 0 1 1-6.219-8.56" />
    </svg>
  )
}
