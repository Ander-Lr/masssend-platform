import { useEffect, useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { useWhatsapp } from '../../context/WhatsappContext'
import { modulosVisibles } from '../../modulos'
import Insignia, { Punto } from '../ui/Insignia'
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

// Estado del numero de la plataforma, como en el base. Solo lo ve staff.
function EstadoWhatsapp({ contraido }) {
  const { conectado } = useWhatsapp()
  if (conectado === null) return null
  const texto = conectado ? 'WA Conectado' : 'WA Desconectado'
  if (contraido) {
    return <div className="mb-1 flex justify-center py-2" title={texto}><Punto encendido={conectado} parpadea /></div>
  }
  return (
    <div className={`mx-3 mb-1 flex items-center gap-[7px] rounded-lg border px-3 py-2 text-[0.72rem] font-semibold
      ${conectado ? 'border-emerald-500/25 bg-emerald-500/10 text-emerald-600' : 'border-red-500/20 bg-red-500/[0.08] text-red-600'}`}>
      <Punto encendido={conectado} parpadea />{texto}
    </div>
  )
}

export default function Layout() {
  const { usuario, cerrarSesion } = useAuth()
  const [contraido, setContraido] = useState(leerContraido)

  useEffect(() => {
    try { localStorage.setItem(CLAVE_CONTRAIDO, contraido ? '1' : '0') } catch { /* sin almacenamiento */ }
  }, [contraido])

  return (
    <div className="flex h-screen w-full">
      <aside className={`flex shrink-0 flex-col overflow-hidden border-r border-gray-200 bg-white transition-[width] duration-200 ${contraido ? 'w-16' : 'w-[220px]'}`}>
        <div className={`flex min-h-[60px] items-center border-b border-gray-200 ${contraido ? 'justify-center' : 'justify-between pl-5 pr-4'}`}>
          {!contraido && <span className="whitespace-nowrap text-[1.1rem] font-bold text-tinta">Mass<span className="text-marca">Send</span></span>}
          <button
            onClick={() => setContraido(c => !c)}
            title={contraido ? 'Expandir menú' : 'Contraer menú'}
            aria-label={contraido ? 'Expandir menú' : 'Contraer menú'}
            className="flex items-center justify-center rounded-md p-1 text-gray-500 hover:bg-gray-100"
          >
            <Chevron contraido={contraido} />
          </button>
        </div>

        <nav className="flex flex-1 flex-col gap-0.5 overflow-y-auto py-3">
          {modulosVisibles(usuario).map(m => (
            <NavLink
              key={m.id}
              to={m.ruta}
              end={m.ruta === '/'}
              title={contraido ? m.label : ''}
              className={({ isActive }) => `flex items-center whitespace-nowrap border-l-[3px] text-[0.9rem] transition-colors
                ${contraido ? 'justify-center py-[11px]' : 'gap-2.5 px-5 py-2.5'}
                ${isActive ? 'border-marca bg-marca-suave font-semibold text-marca' : 'border-transparent text-gray-700 hover:bg-gray-50'}`}
            >
              <span className="flex shrink-0">{ICONOS[m.id]}</span>
              {!contraido && <span>{m.label}</span>}
            </NavLink>
          ))}
        </nav>

        <EstadoWhatsapp contraido={contraido} />

        <div className={`flex flex-col gap-2 border-t border-gray-200 ${contraido ? 'items-center py-3' : 'px-4 py-3'}`}>
          {!contraido && (
            <div className="flex flex-col overflow-hidden text-[0.74rem] text-gray-500">
              <strong className="truncate text-[0.82rem] text-tinta">{usuario.nombre}</strong>
              <span className="truncate">{usuario.correo}</span>
              {usuario.es_staff && <Insignia color="verde" className="mt-1 self-start">Staff</Insignia>}
            </div>
          )}
          <button
            onClick={cerrarSesion}
            title={contraido ? 'Cerrar sesión' : ''}
            className={`flex items-center justify-center gap-1.5 rounded-[7px] border border-gray-200 bg-gray-100 text-[0.8rem] font-semibold text-gray-700 hover:bg-gray-200
              ${contraido ? 'size-[38px]' : 'w-full p-2'}`}
          >
            {ICONOS.salir}
            {!contraido && 'Cerrar sesión'}
          </button>
        </div>
      </aside>

      <main className="flex flex-1 overflow-hidden">
        <Outlet />
      </main>
    </div>
  )
}
