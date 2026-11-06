export function Etiqueta({ children }) {
  return <span className="mb-0.5 mr-1 inline-block rounded-full bg-purple-100 px-2 py-px text-[0.7rem] text-violet-600">{children}</span>
}

export default function Etiquetas({ lista, vacio = 'Sin etiqueta' }) {
  if (!lista?.length) return <span className="text-[0.78rem] text-gray-300">{vacio}</span>
  return lista.map(e => <Etiqueta key={e}>{e}</Etiqueta>)
}
