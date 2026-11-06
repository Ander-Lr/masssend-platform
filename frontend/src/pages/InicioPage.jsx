import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { modulosVisibles } from '../modulos'
import { saldo } from '../api/creditos'
import { listarCampanas } from '../api/campanas'
import Insignia from '../components/ui/Insignia'
import Estadistica, { Estadisticas } from '../components/ui/Estadistica'

// Resumen de la cuenta: cada dato se pide aparte para que uno lento no frene a los demas.
function useResumen() {
  const [resumen, setResumen] = useState({})
  useEffect(() => {
    const guardar = clave => valor => setResumen(r => ({ ...r, [clave]: valor }))
    const contar = r => (r.pagina.tiene_mas ? `${r.datos.length}+` : r.datos.length)
    saldo().then(s => guardar('creditos')(s.disponible)).catch(() => {})
    listarCampanas({ estado: 'en_curso', limite: 100 }).then(r => guardar('enCurso')(contar(r))).catch(() => {})
    listarCampanas({ estado: 'borrador', limite: 100 }).then(r => guardar('borradores')(contar(r))).catch(() => {})
    listarCampanas({ estado: 'completada', limite: 100 }).then(r => guardar('completadas')(contar(r))).catch(() => {})
  }, [])
  return resumen
}

const saludoDelMomento = () => {
  const hora = new Date().getHours()
  return hora < 12 ? 'Buenos días' : hora < 19 ? 'Buenas tardes' : 'Buenas noches'
}

export default function InicioPage() {
  const { usuario } = useAuth()
  const navigate = useNavigate()
  const accesos = modulosVisibles(usuario).filter(m => m.titulo)
  const resumen = useResumen()
  const metricas = [
    { clave: 'creditos', label: 'Créditos disponibles', color: 'verde', ruta: '/creditos' },
    { clave: 'enCurso', label: 'Campañas enviándose', color: 'morado', ruta: '/campanas' },
    { clave: 'borradores', label: 'Borradores listos', color: 'normal', ruta: '/campanas' },
    { clave: 'completadas', label: 'Campañas completadas', color: 'azul', ruta: '/campanas' },
  ]

  return (
    <div className="flex-1 overflow-y-auto bg-slate-50 px-4 py-6 sm:px-10 sm:py-9">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="flex size-14 shrink-0 items-center justify-center rounded-full bg-marca text-[1.4rem] font-bold text-white">
            {usuario.nombre?.[0]?.toUpperCase() || 'U'}
          </div>
          <div>
            <p className="text-[0.85rem] text-gray-400">{saludoDelMomento()},</p>
            <h1 className="text-2xl font-bold">{usuario.nombre}</h1>
          </div>
        </div>
        <Insignia color={usuario.mfa_activo ? 'verde' : 'roja'} grande>
          {usuario.mfa_activo ? 'Cuenta protegida con doble factor' : 'Doble factor desactivado'}
        </Insignia>
      </div>

      <Estadisticas className="mt-6 mb-0">
        {metricas.map(m => (
          <Estadistica key={m.clave} valor={resumen[m.clave] ?? '...'} etiqueta={m.label} color={m.color} onClick={() => navigate(m.ruta)} />
        ))}
      </Estadisticas>

      <p className="mt-7 mb-5 text-[0.95rem] text-gray-500">¿Qué quieres hacer hoy?</p>

      <div className="grid grid-cols-[repeat(auto-fill,minmax(220px,1fr))] gap-5">
        {accesos.map(m => (
          <button
            key={m.id}
            style={{ '--c': m.color }}
            className="rounded-2xl border border-(--c)/20 bg-(--c)/8 px-5 py-6 text-left transition duration-200 hover:-translate-y-1 hover:shadow-[0_8px_24px_color-mix(in_srgb,var(--c)_15%,transparent)]"
            onClick={() => navigate(m.ruta)}
          >
            <h3 className="mb-1.5 text-base font-bold text-(--c)">{m.titulo}</h3>
            <p className="text-[0.82rem] leading-normal text-gray-500">{m.desc}</p>
          </button>
        ))}
      </div>
    </div>
  )
}
