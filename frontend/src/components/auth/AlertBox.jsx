import { cx } from '../ui/clases'
const TIPOS = {
  error: 'bg-red-100 text-red-800',
  success: 'bg-green-100 text-green-800',
  info: 'bg-blue-50 text-blue-800',
  advertencia: 'border border-orange-200 bg-orange-50 text-amber-800',
}

export default function AlertBox({ type = 'error', className = '', children }) {
  if (!children) return null
  return (
    <div className={cx(`mb-4 rounded-lg px-3.5 py-2.5 text-[0.82rem] leading-relaxed ${TIPOS[type] || TIPOS.error}`, className)} role={type === 'error' ? 'alert' : 'status'}>
      {children}
    </div>
  )
}
