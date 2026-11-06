import { useEffect, useState } from 'react'
import { sileo } from 'sileo'
import AlertBox from '../components/auth/AlertBox'
import { confirmar } from '../components/ui/confirmar'
import { cerrarSesionWhatsapp, estadoWhatsapp, vincularWhatsapp } from '../api/envio'
import { useWhatsapp } from '../context/WhatsappContext'

const PASOS = [
  'Si hay un número activo, desconéctalo primero.',
  'Escribe el número con su código de país y solicita el código.',
  'En el teléfono abre WhatsApp, Dispositivos vinculados, Vincular con número de teléfono.',
  'Escribe el código de 8 caracteres. Cuando el estado cambie a Conectado, ya está listo.',
]

function EstadoConexion({ conectado }) {
  if (conectado === null) return <span className="insignia insignia-gris">Consultando...</span>
  return (
    <span className={`insignia ${conectado ? 'insignia-verde' : 'insignia-roja'}`} style={{ padding: '6px 16px', fontSize: '0.85rem' }}>
      <span className={`wa-dot ${conectado ? 'on' : 'off'}`} />
      {conectado ? 'Conectado' : 'Desconectado'}
    </span>
  )
}

// Numero de WhatsApp de toda la plataforma. Solo staff.
export default function WhatsAppPage() {
  const { conectado, codigo_vinculacion: codigoGlobal, setEstado } = useWhatsapp()
  const [telefono, setTelefono] = useState('593')
  const [codigo, setCodigo] = useState('')
  const [mensaje, setMensaje] = useState('')
  const [error, setError] = useState('')
  const [pidiendo, setPidiendo] = useState(false)
  const [desconectando, setDesconectando] = useState(false)

  // Mientras se vincula se consulta cada 3 segundos para mostrar el codigo y el cambio de estado.
  useEffect(() => {
    if (conectado) return undefined
    let vigente = true
    const t = setInterval(() => estadoWhatsapp().then(e => vigente && setEstado(e)).catch(() => {}), 3000)
    return () => { vigente = false; clearInterval(t) }
  }, [conectado, setEstado])

  const solicitar = async e => {
    e.preventDefault()
    setError('')
    setMensaje('')
    setPidiendo(true)
    try {
      const r = await vincularWhatsapp(telefono)
      if (r.codigo) setCodigo(r.codigo)
      setMensaje(r.detalle)
    } catch (err) {
      setError(err.mensajeUsuario)
    } finally {
      setPidiendo(false)
    }
  }

  const desconectar = () => confirmar({
    titulo: '¿Desconectar WhatsApp?',
    descripcion: 'Las campañas no podrán enviarse hasta vincular un número otra vez.',
    etiqueta: 'Desconectar',
    alConfirmar: async () => {
      setDesconectando(true)
      try {
        const r = await cerrarSesionWhatsapp()
        setCodigo('')
        setEstado(e => ({ ...e, conectado: false }))
        sileo.success({ title: 'WhatsApp desconectado', description: r.detalle })
      } catch (err) {
        sileo.error({ title: 'No se pudo desconectar', description: err.mensajeUsuario })
      } finally {
        setDesconectando(false)
      }
    },
  })

  const codigoVisible = conectado ? '' : codigo || codigoGlobal || ''
  const partes = codigoVisible ? [codigoVisible.slice(0, 4), codigoVisible.slice(4)] : ['----', '----']

  return (
    <div className="pagina" style={{ background: '#f8f9fa' }}>
      <h1 className="pagina-titulo">Conexión WhatsApp</h1>
      <p className="pagina-subtitulo" style={{ marginBottom: 28 }}>
        Vincula el número de WhatsApp desde el que la plataforma envía las campañas y el chat.
      </p>

      <div className="rejilla" style={{ maxWidth: 820, alignItems: 'start' }}>
        <div className="tarjeta">
          <p className="titulo-seccion">Estado de la conexión</p>
          <EstadoConexion conectado={conectado} />
          <p style={{ fontWeight: 600, fontSize: '0.82rem', margin: '22px 0 10px' }}>Cómo vincular un número</p>
          {PASOS.map((paso, i) => (
            <div key={paso} className="paso">
              <span>{i + 1}</span>
              <p>{paso}</p>
            </div>
          ))}
          <div className="aviso" style={{ background: '#fef3c7', borderLeft: '4px solid #f59e0b', color: '#92400e', margin: '16px 0 20px' }}>
            El historial de mensajes y los contactos no se borran al cambiar el número.
          </div>
          <button className="boton boton-peligro boton-bloque" disabled={!conectado || desconectando} onClick={desconectar}>
            {desconectando ? 'Desconectando...' : 'Desconectar número actual'}
          </button>
        </div>

        <div className="tarjeta">
          {conectado ? (
            <div style={{ textAlign: 'center', padding: '28px 10px' }}>
              <div className="circulo-ok">
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg>
              </div>
              <p style={{ fontWeight: 700, color: '#065f46' }}>WhatsApp conectado</p>
              <p className="texto-suave" style={{ fontSize: '0.8rem', marginTop: 4 }}>El número está vinculado y listo para enviar mensajes.</p>
            </div>
          ) : (
            <form onSubmit={solicitar}>
              <p className="texto-suave" style={{ fontSize: '0.82rem', marginBottom: 16 }}>Vincula por número de teléfono, sin escanear un QR.</p>
              <div className="campo">
                <label>Número con código de país, sin el +</label>
                <input className="entrada" value={telefono} onChange={e => setTelefono(e.target.value.replace(/\D/g, ''))} placeholder="593XXXXXXXXX" inputMode="tel" maxLength={15} required />
              </div>
              <button type="submit" className="boton boton-bloque" style={{ background: '#7c3aed', color: '#fff', marginBottom: 16 }} disabled={pidiendo || telefono.length < 8}>
                {pidiendo ? 'Solicitando...' : 'Solicitar código de vinculación'}
              </button>
              <AlertBox>{error}</AlertBox>
              <div style={{ textAlign: 'center' }}>
                <p className="texto-suave" style={{ fontSize: '0.78rem', marginBottom: 10 }}>Código de vinculación</p>
                <div className="codigo-vinculacion">
                  <span>{partes[0]}</span><span className="guion">-</span><span>{partes[1]}</span>
                </div>
                {mensaje && <p className="texto-suave" style={{ fontSize: '0.78rem', marginTop: 10 }}>{mensaje}</p>}
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  )
}
