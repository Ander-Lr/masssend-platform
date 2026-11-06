export default function Etiquetas({ lista, vacio = 'Sin etiqueta' }) {
  if (!lista?.length) return <span style={{ color: '#d1d5db', fontSize: '0.78rem' }}>{vacio}</span>
  return lista.map(e => <span key={e} className="etiqueta">{e}</span>)
}
