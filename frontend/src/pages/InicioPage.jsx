import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { modulosVisibles } from '../modulos'

const saludoDelMomento = () => {
  const hora = new Date().getHours()
  return hora < 12 ? 'Buenos días' : hora < 19 ? 'Buenas tardes' : 'Buenas noches'
}

export default function InicioPage() {
  const { usuario } = useAuth()
  const navigate = useNavigate()
  const accesos = modulosVisibles(usuario).filter(m => m.titulo)

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

      <p className="texto-suave" style={{ fontSize: '0.95rem', margin: '20px 0 28px' }}>¿Qué quieres hacer hoy?</p>

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
