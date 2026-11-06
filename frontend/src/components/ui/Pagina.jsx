// Contenedor de cada seccion con su titulo y acciones.
export default function Pagina({ titulo, subtitulo, acciones, fondo = 'bg-panel', className = '', children }) {
  return (
    <div className={`flex-1 overflow-y-auto px-4 py-5 sm:px-8 sm:py-7 ${fondo} ${className}`}>
      {(titulo || acciones) && (
        <div className="mb-5 flex flex-wrap items-center justify-between gap-4">
          <div>
            {titulo && <h1 className="text-[1.4rem] font-bold text-tinta">{titulo}</h1>}
            {subtitulo && <p className="mt-1 text-[0.88rem] text-gray-500">{subtitulo}</p>}
          </div>
          {acciones && <div className="flex flex-wrap gap-2.5">{acciones}</div>}
        </div>
      )}
      {children}
    </div>
  )
}

export function Vacio({ children }) {
  return <div className="px-5 py-14 text-center text-gray-400">{children}</div>
}
