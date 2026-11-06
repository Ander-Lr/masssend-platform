// Botones del proyecto base expresados con utilidades de Tailwind.
import { claseBoton, cx } from './clases'

export default function Boton({ variante, tamano, bloque, className = '', type = 'button', ...props }) {
  return <button type={type} className={cx(`${claseBoton({ variante, tamano, bloque })}`, className)} {...props} />
}

// Acciones pequenas de tablas y tarjetas.
const MINI = {
  gris: 'bg-gray-100 text-gray-700',
  amarillo: 'bg-amber-100 text-amber-800',
  verde: 'bg-emerald-100 text-emerald-800',
  rojo: 'bg-red-100 text-red-800',
  indigo: 'bg-indigo-500 text-white',
}

export function BotonMini({ color = 'gris', grande = false, className = '', ...props }) {
  return (
    <button
      type="button"
      className={cx(`inline-flex items-center gap-1.5 whitespace-nowrap rounded-md border-0 font-semibold disabled:opacity-70
        ${grande ? 'px-3.5 py-1.5 text-[0.78rem]' : 'px-2.5 py-1 text-[0.72rem]'} ${MINI[color]}`, className)}
      {...props}
    />
  )
}

export function BotonEnlace({ peligro = false, className = '', ...props }) {
  return (
    <button
      type="button"
      className={cx(`border-0 bg-transparent p-0 text-[0.82rem] font-semibold underline ${peligro ? 'text-red-800' : 'text-marca-enlace'}`, className)}
      {...props}
    />
  )
}
