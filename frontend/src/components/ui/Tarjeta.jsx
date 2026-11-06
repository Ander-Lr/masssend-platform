export default function Tarjeta({ titulo, children, className = '' }) {
  return (
    <div className={`rounded-xl border border-gray-200 bg-white p-6 ${className}`}>
      {titulo && <h2 className="mb-1.5 text-base font-bold text-tinta">{titulo}</h2>}
      {children}
    </div>
  )
}
