import Boton from '../ui/Boton'

export default function PrimaryButton({ children, loading, disabled, type = 'submit', onClick }) {
  return (
    <Boton type={type} onClick={onClick} disabled={disabled || loading} bloque className="p-[11px] text-[0.9rem]">
      {children}
    </Boton>
  )
}
