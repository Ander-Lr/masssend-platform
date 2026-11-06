const COLORES = {
  verde: 'text-emerald-500', azul: 'text-blue-500', rojo: 'text-red-500', morado: 'text-violet-500', normal: 'text-tinta',
}

export function Estadisticas({ children, className = '' }) {
  return <div className={`mb-7 grid grid-cols-[repeat(auto-fit,minmax(150px,1fr))] gap-4 ${className}`}>{children}</div>
}

export default function Estadistica({ valor, etiqueta, color = 'normal', onClick }) {
  const Elemento = onClick ? 'button' : 'div'
  return (
    <Elemento onClick={onClick} className={`rounded-xl border border-gray-200 bg-white p-5 text-center ${onClick ? 'transition-shadow hover:shadow-md' : ''}`}>
      <div className={`text-[2rem] font-bold leading-tight ${COLORES[color]}`}>{valor}</div>
      <div className="mt-1 text-[0.78rem] text-gray-400">{etiqueta}</div>
    </Elemento>
  )
}
