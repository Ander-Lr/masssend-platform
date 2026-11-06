import { useRef, useState } from 'react'
import { sileo } from 'sileo'
import AlertBox from '../components/auth/AlertBox'
import FormField from '../components/auth/FormField'
import Boton, { BotonEnlace } from '../components/ui/Boton'
import Pagina from '../components/ui/Pagina'
import Tarjeta from '../components/ui/Tarjeta'
import { Ayuda, Etiqueta, claseEntrada } from '../components/ui/Campo'
import { ACEPTA_ADJUNTO_CORREO, enviarNotificacion } from '../api/notificaciones'

const VACIO = { destinatario: '', asunto: '', titulo: '', mensaje: '', firma: '' }

// Correo con la plantilla de MassSend a cualquier usuario. Solo staff.
export default function NotificacionesPage() {
  const [datos, setDatos] = useState(VACIO)
  const [archivo, setArchivo] = useState(null)
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)
  const entradaArchivo = useRef(null)
  const campo = clave => valor => setDatos(d => ({ ...d, [clave]: valor }))

  const enviar = async e => {
    e.preventDefault()
    setError('')
    setEnviando(true)
    try {
      const r = await enviarNotificacion({ ...datos, archivo })
      sileo.success({ title: 'Notificación en cola', description: `Se enviará a ${r.destinatario}` })
      setDatos(VACIO)
      setArchivo(null)
    } catch (err) {
      setError(err.mensajeUsuario)
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Pagina titulo="Notificaciones por correo" subtitulo="Envía un correo con la plantilla de MassSend. Se procesa en segundo plano por la cola de correos." fondo="bg-lienzo">
      <Tarjeta className="max-w-[560px]">
        <form onSubmit={enviar}>
          <FormField label="Destinatario" type="email" value={datos.destinatario} onChange={campo('destinatario')} placeholder="usuario@correo.com" autoFocus />
          <FormField label="Asunto" value={datos.asunto} onChange={campo('asunto')} maxLength={500} />
          <FormField label="Título" value={datos.titulo} onChange={campo('titulo')} maxLength={500} />
          <div className="mb-4">
            <Etiqueta>Mensaje</Etiqueta>
            <textarea className={`${claseEntrada} min-h-32 resize-y leading-normal`} value={datos.mensaje} onChange={e => campo('mensaje')(e.target.value)} maxLength={10000} required />
          </div>
          <FormField label="Firma (opcional)" value={datos.firma} onChange={campo('firma')} required={false} placeholder="Equipo MassSend" maxLength={100} />
          <div className="mb-5">
            <Etiqueta>Adjunto (opcional)</Etiqueta>
            <div className="flex flex-wrap items-center gap-2.5">
              <Boton variante="secundario" tamano="sm" onClick={() => entradaArchivo.current?.click()}>{archivo ? 'Cambiar archivo' : 'Elegir archivo'}</Boton>
              <span className="text-[0.78rem] text-gray-500">{archivo ? archivo.name : 'PDF, PNG, JPG, DOCX o XLSX'}</span>
              {archivo && <BotonEnlace peligro onClick={() => setArchivo(null)}>Quitar</BotonEnlace>}
            </div>
            <input ref={entradaArchivo} type="file" accept={ACEPTA_ADJUNTO_CORREO} className="hidden" onChange={e => { setArchivo(e.target.files[0] || null); e.target.value = '' }} />
            <Ayuda>El backend comprueba el tipo real del archivo y su tamaño máximo.</Ayuda>
          </div>
          <AlertBox>{error}</AlertBox>
          <Boton type="submit" disabled={enviando}>{enviando ? 'Enviando...' : 'Enviar notificación'}</Boton>
        </form>
      </Tarjeta>
    </Pagina>
  )
}
