// Tabla con el estilo del base: cabecera gris y filas separadas por una linea suave.
export function Tabla({ children, className = '', atenuada = false }) {
  return (
    <table className={`w-full border-collapse text-[0.83rem] [&_td]:border-b [&_td]:border-gray-100 [&_td]:px-4 [&_td]:py-2.5
      [&_th]:bg-gray-50 [&_th]:px-4 [&_th]:py-2.5 [&_th]:text-left [&_th]:text-[0.78rem] [&_th]:font-semibold [&_th]:text-gray-500
      ${atenuada ? 'opacity-60' : ''} ${className}`}>
      {children}
    </table>
  )
}

export function ContenedorTabla({ titulo, children, className = '' }) {
  return (
    <div className={`overflow-x-auto rounded-xl bg-white shadow-[0_1px_3px_rgba(0,0,0,0.06)] ${className}`}>
      {titulo && <h2 className="border-b border-gray-200 px-5 py-4 text-base font-bold">{titulo}</h2>}
      {children}
    </div>
  )
}

export function Paginacion({ pagina, hayAnterior, haySiguiente, cargando, onAnterior, onSiguiente }) {
  const clase = 'rounded-lg border border-gray-200 bg-white px-3.5 py-1.5 text-[0.85rem] font-semibold text-gray-700 hover:bg-gray-50 disabled:opacity-50'
  return (
    <div className="mt-4 flex items-center justify-center gap-2 text-[0.85rem] text-gray-600">
      <button className={clase} disabled={!hayAnterior || cargando} onClick={onAnterior}>Anterior</button>
      <span className="px-2">Página {pagina}</span>
      <button className={clase} disabled={!haySiguiente || cargando} onClick={onSiguiente}>Siguiente</button>
    </div>
  )
}

export function BarraSeleccion({ texto, children }) {
  return (
    <div className="mb-3 flex flex-wrap items-center gap-3 rounded-[10px] border border-indigo-300 bg-indigo-50 px-4 py-2.5">
      <strong className="text-[0.85rem] text-indigo-700">{texto}</strong>
      {children}
    </div>
  )
}
