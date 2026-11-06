// Ventana modal con titulo y boton de cierre. Se cierra con Escape.
import { useEffect } from 'react'

export default function Modal({ titulo, subtitulo, onCerrar, children, ancho = 440 }) {
  useEffect(() => {
    const alPresionar = e => { if (e.key === 'Escape') onCerrar() }
    window.addEventListener('keydown', alPresionar)
    return () => window.removeEventListener('keydown', alPresionar)
  }, [onCerrar])

  return (
    <div className="modal-fondo" onMouseDown={e => { if (e.target === e.currentTarget) onCerrar() }}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={titulo} style={{ maxWidth: ancho, padding: 28 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20, gap: 12 }}>
          <div>
            <h2 style={{ fontSize: '1rem', fontWeight: 700 }}>{titulo}</h2>
            {subtitulo && <p className="texto-suave" style={{ fontSize: '0.78rem', marginTop: 4 }}>{subtitulo}</p>}
          </div>
          <button className="modal-cerrar" onClick={onCerrar} aria-label="Cerrar">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}
