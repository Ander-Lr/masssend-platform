import { useEffect, useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { modulosVisibles } from '../../modulos'
import { ICONOS } from './iconos'

const CLAVE_CONTRAIDO = 'masssend.menuContraido'

const leerContraido = () => {
  try {
    return localStorage.getItem(CLAVE_CONTRAIDO) === '1' || window.innerWidth < 720
  } catch {
    return false
  }
}

function Chevron({ contraido }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points={contraido ? '9 18 15 12 9 6' : '15 18 9 12 15 6'} />
    </svg>
  )
}

export default function Layout() {
  const { usuario, cerrarSesion } = useAuth()
  const [contraido, setContraido] = useState(leerContraido)
  const ancho = contraido ? 64 : 220

  useEffect(() => {
    try { localStorage.setItem(CLAVE_CONTRAIDO, contraido ? '1' : '0') } catch { /* sin almacenamiento */ }
  }, [contraido])

  return (
    <div className="layout">
      <aside className="menu" style={{ width: ancho, minWidth: ancho }}>
        <div className="menu-cabecera" style={{ justifyContent: contraido ? 'center' : 'space-between', padding: contraido ? '18px 0' : '18px 16px 18px 20px' }}>
          {!contraido && (
            <span className="menu-marca">Mass<span>Send</span></span>
          )}
          <button
            className="menu-plegar"
            onClick={() => setContraido(c => !c)}
            title={contraido ? 'Expandir menú' : 'Contraer menú'}
            aria-label={contraido ? 'Expandir menú' : 'Contraer menú'}
          >
            <Chevron contraido={contraido} />
          </button>
        </div>

        <nav className="menu-nav">
          {modulosVisibles(usuario).map(m => (
            <NavLink
              key={m.id}
              to={m.ruta}
              end={m.ruta === '/'}
              title={contraido ? m.label : ''}
              className={({ isActive }) => `menu-item${isActive ? ' activo' : ''}${contraido ? ' contraido' : ''}`}
            >
              <span style={{ flexShrink: 0, display: 'flex' }}>{ICONOS[m.id]}</span>
              {!contraido && <span>{m.label}</span>}
            </NavLink>
          ))}
        </nav>

        <div className="menu-pie" style={{ alignItems: contraido ? 'center' : 'stretch', padding: contraido ? '12px 0' : '12px 16px' }}>
          {!contraido && (
            <div className="menu-usuario">
              <strong>{usuario.nombre}</strong>
              <span>{usuario.correo}</span>
              {usuario.es_staff && <span className="insignia insignia-verde" style={{ alignSelf: 'flex-start', marginTop: 4 }}>Staff</span>}
            </div>
          )}
          <button
            className="boton boton-secundario"
            onClick={cerrarSesion}
            title={contraido ? 'Cerrar sesión' : ''}
            style={contraido ? { width: 38, height: 38, padding: 0 } : { width: '100%', padding: 8, fontSize: '0.8rem' }}
          >
            {ICONOS.salir}
            {!contraido && 'Cerrar sesión'}
          </button>
        </div>
      </aside>

      <main className="main">
        <Outlet />
      </main>
    </div>
  )
}
