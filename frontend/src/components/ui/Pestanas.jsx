export default function Pestanas({ opciones, valor, onCambiar }) {
  return (
    <div className="mb-4 flex flex-wrap gap-1.5" role="tablist">
      {opciones.map(o => (
        <button
          key={o.valor}
          role="tab"
          aria-selected={valor === o.valor}
          onClick={() => onCambiar(o.valor)}
          className={`rounded-full border px-3.5 py-1.5 text-[0.82rem] transition-colors ${valor === o.valor ? 'border-tinta bg-tinta text-white' : 'border-gray-200 bg-white text-gray-700 hover:border-gray-300'}`}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}
