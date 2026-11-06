export default function AlertBox({ type = 'error', children }) {
  if (!children) return null
  const clase = { success: 'aviso-exito', info: 'aviso-info' }[type] || 'aviso-error'
  return <div className={`aviso ${clase}`} role={type === 'error' ? 'alert' : 'status'}>{children}</div>
}
