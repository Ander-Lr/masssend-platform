export default function PrimaryButton({ children, loading, disabled, type = 'submit', onClick }) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled || loading}
      className="boton boton-primario boton-bloque"
      style={{ padding: 11, fontSize: '0.9rem' }}
    >
      {children}
    </button>
  )
}
