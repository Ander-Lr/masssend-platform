import { BotonEnlace } from '../ui/Boton'

export default function LinkButton({ children, onClick, peligro = false }) {
  return <BotonEnlace onClick={onClick} peligro={peligro}>{children}</BotonEnlace>
}
