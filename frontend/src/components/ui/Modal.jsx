// Ventana modal con titulo y boton de cierre. Se cierra con Escape o al hacer clic fuera.
import { useEffect } from 'react'

export function Cerrar({ onClick }) {
  return (
    <button type="button" onClick={onClick} aria-label="Cerrar" className="flex rounded-md p-0.5 text-gray-400 hover:bg-gray-100">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
    </button>
  )
}

export function Fondo({ children, onCerrar }) {
  return (
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center bg-slate-900/55 p-4 backdrop-blur-[2px]"
      onMouseDown={e => { if (onCerrar && e.target === e.currentTarget) onCerrar() }}
    >
      {children}
    </div>
  )
}

export default function Modal({ titulo, subtitulo, onCerrar, children, ancho = 'max-w-md' }) {
  useEffect(() => {
    const alPresionar = e => { if (e.key === 'Escape') onCerrar() }
    window.addEventListener('keydown', alPresionar)
    return () => window.removeEventListener('keydown', alPresionar)
  }, [onCerrar])

  return (
    <Fondo onCerrar={onCerrar}>
      <div role="dialog" aria-modal="true" aria-label={titulo} className={`max-h-[92vh] w-full overflow-y-auto rounded-[14px] bg-white p-7 shadow-2xl ${ancho}`}>
        <div className="mb-5 flex items-start justify-between gap-3">
          <div>
            <h2 className="text-base font-bold">{titulo}</h2>
            {subtitulo && <p className="mt-1 text-[0.78rem] text-gray-500">{subtitulo}</p>}
          </div>
          <Cerrar onClick={onCerrar} />
        </div>
        {children}
      </div>
    </Fondo>
  )
}
