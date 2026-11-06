import { useEffect, useState } from 'react'
import AlertBox from '../auth/AlertBox'
import Modal from '../ui/Modal'
import Boton from '../ui/Boton'
import Estadistica from '../ui/Estadistica'
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
      {!datos && !error && <p className="text-[0.88rem] text-gray-500">Calculando destinatarios...</p>}
      {datos && (
        <div className="mb-4 grid grid-cols-2 gap-4">
          <Estadistica valor={datos.destinatarios} etiqueta="Destinatarios" color="azul" />
          <Estadistica valor={datos.disponible} etiqueta="Créditos disponibles" color={sinSaldo ? 'rojo' : 'verde'} />
        </div>
      )}
      {datos && datos.destinatarios === 0 && <AlertBox type="info">Ningún contacto activo coincide con las etiquetas de la campaña.</AlertBox>}
      {sinSaldo && <AlertBox type="info">Cada mensaje usa un crédito. Si te faltan créditos, el backend rechazará el lanzamiento.</AlertBox>}
      <AlertBox>{error}</AlertBox>
      <p className="mb-4 text-[0.8rem] leading-normal text-gray-500">
        Los créditos se reservan al lanzar y se descuentan por cada mensaje enviado. Si cancelas, se liberan los que no se usaron.
      </p>
      <div className="flex justify-end gap-2.5">
        <Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton>
        <Boton variante="indigo" disabled={!datos || datos.destinatarios === 0 || lanzando} onClick={confirmar}>
          {lanzando ? 'Lanzando...' : 'Lanzar campaña'}
        </Boton>
      </div>
    </Modal>
  )
}
