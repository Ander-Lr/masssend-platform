import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { modulosVisibles } from '../modulos'
import { saldo } from '../api/creditos'
import { listarCampanas } from '../api/campanas'

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
    { clave: 'creditos', label: 'Créditos disponibles', clase: 'green', ruta: '/creditos' },
    { clave: 'enCurso', label: 'Campañas enviándose', clase: 'purple', ruta: '/campanas' },
    { clave: 'borradores', label: 'Borradores listos', clase: '', ruta: '/campanas' },
    { clave: 'completadas', label: 'Campañas completadas', clase: 'blue', ruta: '/campanas' },
  ]

  return (
    <div className="pagina" style={{ background: '#f8fafc', padding: '36px 40px' }}>
      <div className="pagina-encabezado" style={{ alignItems: 'center', marginBottom: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <div className="avatar">{usuario.nombre?.[0]?.toUpperCase() || 'U'}</div>
          <div>
            <p className="texto-suave" style={{ fontSize: '0.85rem' }}>{saludoDelMomento()},</p>
            <h1 style={{ fontSize: '1.5rem', fontWeight: 700 }}>{usuario.nombre}</h1>
          </div>
        </div>
        <span className={`insignia ${usuario.mfa_activo ? 'insignia-verde' : 'insignia-roja'}`} style={{ padding: '8px 16px', fontSize: '0.8rem' }}>
          {usuario.mfa_activo ? 'Cuenta protegida con doble factor' : 'Doble factor desactivado'}
        </span>
      </div>

      <div className="stats-grid" style={{ marginTop: 24, marginBottom: 0 }}>
        {metricas.map(m => (
          <button key={m.clave} className={`stat-card ${m.clase}`} style={{ cursor: 'pointer', fontFamily: 'inherit' }} onClick={() => navigate(m.ruta)}>
            <div className="stat-num">{resumen[m.clave] ?? '...'}</div>
            <div className="stat-label">{m.label}</div>
          </button>
        ))}
      </div>

      <p className="texto-suave" style={{ fontSize: '0.95rem', margin: '28px 0 20px' }}>¿Qué quieres hacer hoy?</p>

      <div className="accesos">
        {accesos.map(m => (
          <button
            key={m.id}
            className="acceso"
            style={{ background: `${m.color}14`, borderColor: `${m.color}33`, '--color': m.color }}
            onClick={() => navigate(m.ruta)}
          >
            <h3 style={{ color: m.color }}>{m.titulo}</h3>
            <p>{m.desc}</p>
          </button>
        ))}
      </div>
    </div>
  )
}
