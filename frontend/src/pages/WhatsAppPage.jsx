import { useEffect, useState } from 'react'
import { sileo } from 'sileo'
import AlertBox from '../components/auth/AlertBox'
import Boton from '../components/ui/Boton'
import Insignia, { Punto } from '../components/ui/Insignia'
import Pagina from '../components/ui/Pagina'
import Tarjeta from '../components/ui/Tarjeta'
import { Etiqueta, claseEntrada } from '../components/ui/Campo'
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
  if (conectado === null) return <Insignia>Consultando...</Insignia>
  return (
    <Insignia color={conectado ? 'verde' : 'roja'} grande>
      <Punto encendido={conectado} />
      {conectado ? 'Conectado' : 'Desconectado'}
    </Insignia>
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

  // El gateway renueva el codigo si la conexion se reinicia: manda el que informa el servidor.
  const codigoVisible = conectado ? '' : codigoGlobal || codigo || ''
  const partes = codigoVisible ? [codigoVisible.slice(0, 4), codigoVisible.slice(4)] : ['----', '----']

  return (
    <Pagina titulo="Conexión WhatsApp" subtitulo="Vincula el número de WhatsApp desde el que la plataforma envía las campañas y el chat.">
      <div className="mt-2 grid max-w-[820px] grid-cols-[repeat(auto-fit,minmax(280px,1fr))] items-start gap-5">
        <Tarjeta>
          <p className="mb-2.5 text-[0.72rem] font-bold uppercase tracking-wide text-gray-400">Estado de la conexión</p>
          <EstadoConexion conectado={conectado} />
          <p className="mt-[22px] mb-2.5 text-[0.82rem] font-semibold">Cómo vincular un número</p>
          {PASOS.map((paso, i) => (
            <div key={paso} className="mb-2 flex gap-2.5 text-[0.82rem] text-gray-600">
              <span className="flex size-[22px] shrink-0 items-center justify-center rounded-full bg-violet-600 text-[0.72rem] font-bold text-white">{i + 1}</span>
              <p className="pt-0.5 leading-normal">{paso}</p>
            </div>
          ))}
          <div className="mt-4 mb-5 rounded-lg border-l-4 border-amber-500 bg-amber-100 px-3.5 py-2.5 text-[0.78rem] text-amber-800">
            El historial de mensajes y los contactos no se borran al cambiar el número.
          </div>
          <Boton variante="peligro" bloque disabled={!conectado || desconectando} onClick={desconectar}>
            {desconectando ? 'Desconectando...' : 'Desconectar número actual'}
          </Boton>
        </Tarjeta>

        <Tarjeta>
          {conectado ? (
            <div className="px-2.5 py-7 text-center">
              <div className="mx-auto mb-3 flex size-14 items-center justify-center rounded-full bg-emerald-500">
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg>
              </div>
              <p className="font-bold text-emerald-800">WhatsApp conectado</p>
              <p className="mt-1 text-[0.8rem] text-gray-500">El número está vinculado y listo para enviar mensajes.</p>
            </div>
          ) : (
            <form onSubmit={solicitar}>
              <p className="mb-4 text-[0.82rem] text-gray-500">Vincula por número de teléfono, sin escanear un QR.</p>
              <div className="mb-4">
                <Etiqueta>Número con código de país, sin el +</Etiqueta>
                <input className={claseEntrada} value={telefono} onChange={e => setTelefono(e.target.value.replace(/\D/g, ''))} placeholder="593XXXXXXXXX" inputMode="tel" maxLength={15} required />
              </div>
              <Boton type="submit" variante="violeta" bloque className="mb-4" disabled={pidiendo || telefono.length < 8}>
                {pidiendo ? 'Solicitando...' : 'Solicitar código de vinculación'}
              </Boton>
              <AlertBox>{error}</AlertBox>
              <div className="text-center">
                <p className="mb-2.5 text-[0.78rem] text-gray-500">Código de vinculación</p>
                <div className="inline-flex items-center gap-2 rounded-[10px] border-[1.5px] border-dashed border-violet-300 bg-purple-50 px-5 py-3 font-mono text-[1.8rem] font-bold tracking-[0.15em] text-tinta">
                  <span>{partes[0]}</span><span className="text-violet-300">-</span><span>{partes[1]}</span>
                </div>
                {mensaje && <p className="mt-2.5 text-[0.78rem] text-gray-500">{mensaje}</p>}
              </div>
            </form>
          )}
        </Tarjeta>
      </div>
    </Pagina>
  )
}
