export default function LinkButton({ children, onClick, peligro = false }) {
  return (
    <button type="button" onClick={onClick} className={`boton-enlace${peligro ? ' peligro' : ''}`}>
      {children}
    </button>
  )
}
