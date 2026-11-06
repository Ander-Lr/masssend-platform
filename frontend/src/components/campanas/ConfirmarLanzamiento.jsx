import { useEffect, useState } from 'react'
import AlertBox from '../auth/AlertBox'
import Modal from '../ui/Modal'
import { obtenerCampana } from '../../api/campanas'
import { saldo } from '../../api/creditos'

// Antes de lanzar se muestran los destinatarios y el saldo: cada mensaje usa un credito.
export default function ConfirmarLanzamiento({ campana, onCerrar, onConfirmar }) {
  const [datos, setDatos] = useState(null)
  const [error, setError] = useState('')
  const [lanzando, setLanzando] = useState(false)

  useEffect(() => {
    Promise.all([obtenerCampana(campana.id), saldo()])
      .then(([detalle, s]) => setDatos({ destinatarios: detalle.destinatarios, disponible: s.disponible }))
      .catch(err => setError(err.mensajeUsuario))
  }, [campana.id])

  const confirmar = async () => {
    setLanzando(true)
    setError('')
    try {
      await onConfirmar(campana)
    } catch (err) {
      setError(err.estado === 402
        ? `Saldo insuficiente: necesitas ${err.cuerpo.requerido} créditos y tienes ${err.cuerpo.disponible}. Compra un paquete en Créditos.`
        : err.mensajeUsuario)
      setLanzando(false)
    }
  }

  const sinSaldo = datos && datos.destinatarios > datos.disponible
  return (
    <Modal titulo={`¿Lanzar "${campana.nombre}"?`} subtitulo="Los mensajes se envían por WhatsApp en segundo plano." onCerrar={onCerrar}>
      {!datos && !error && <p className="texto-suave">Calculando destinatarios...</p>}
      {datos && (
        <div className="stats-grid" style={{ gridTemplateColumns: '1fr 1fr', marginBottom: 16 }}>
          <div className="stat-card blue"><div className="stat-num">{datos.destinatarios}</div><div className="stat-label">Destinatarios</div></div>
          <div className={`stat-card ${sinSaldo ? 'red' : 'green'}`}><div className="stat-num">{datos.disponible}</div><div className="stat-label">Créditos disponibles</div></div>
        </div>
      )}
      {datos && datos.destinatarios === 0 && <AlertBox type="info">Ningún contacto activo coincide con las etiquetas de la campaña.</AlertBox>}
      {sinSaldo && <AlertBox type="info">Cada mensaje usa un crédito. Si te faltan créditos, el backend rechazará el lanzamiento.</AlertBox>}
      <AlertBox>{error}</AlertBox>
      <p className="texto-suave" style={{ fontSize: '0.8rem', marginBottom: 16, lineHeight: 1.5 }}>
        Los créditos se reservan al lanzar y se descuentan por cada mensaje enviado. Si cancelas, se liberan los que no se usaron.
      </p>
      <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
        <button className="boton boton-secundario" onClick={onCerrar}>Cancelar</button>
        <button className="boton boton-violeta" disabled={!datos || datos.destinatarios === 0 || lanzando} onClick={confirmar}>
          {lanzando ? 'Lanzando...' : 'Lanzar campaña'}
        </button>
      </div>
    </Modal>
  )
}
