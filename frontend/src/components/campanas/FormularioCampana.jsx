import { useEffect, useRef, useState } from 'react'
import { sileo } from 'sileo'
import AlertBox from '../auth/AlertBox'
import FormField from '../auth/FormField'
import Modal from '../ui/Modal'
import { etiquetas as pedirEtiquetas } from '../../api/contactos'
import {
  ACEPTA_ADJUNTO, MAX_MENSAJE, crearCampana, editarCampana, personalizar, revisarAdjunto, subirAdjunto,
} from '../../api/campanas'
import Adjunto from './Adjunto'

// Etiquetas elegidas con un clic entre las que ya existen en los contactos.
function SelectorEtiquetas({ elegidas, onCambiar }) {
  const [disponibles, setDisponibles] = useState([])
  useEffect(() => { pedirEtiquetas().then(r => setDisponibles(r.datos)).catch(() => {}) }, [])
  const alternar = e => onCambiar(elegidas.includes(e) ? elegidas.filter(x => x !== e) : [...elegidas, e])

  return (
    <div className="campo">
      <label>Destinatarios</label>
      {disponibles.length === 0 ? (
        <p className="texto-suave" style={{ fontSize: '0.8rem' }}>Tus contactos no tienen etiquetas: la campaña irá a todos los contactos activos.</p>
      ) : (
        <>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {disponibles.map(e => (
              <button type="button" key={e} className={`chip${elegidas.includes(e) ? ' activo' : ''}`} onClick={() => alternar(e)}>{e}</button>
            ))}
          </div>
          <p className="texto-suave" style={{ fontSize: '0.76rem', marginTop: 6 }}>
            {elegidas.length ? 'Se enviará a los contactos activos con alguna de estas etiquetas.' : 'Sin etiquetas elegidas se envía a todos los contactos activos.'}
          </p>
        </>
      )}
    </div>
  )
}

function VistaPreviaMensaje({ mensaje, archivo, campana }) {
  const texto = personalizar(mensaje, { nombre: 'Juan' })
  return (
    <div className="vista-whatsapp">
      <p className="titulo-violeta" style={{ marginTop: 0, color: '#075e54' }}>Vista previa para un contacto llamado Juan</p>
      <div className="bubble-row out">
        <div className="bubble out" style={{ maxWidth: '90%', whiteSpace: 'pre-wrap' }}>
          {archivo
            ? <div className="adjunto-nuevo">{archivo.name}</div>
            : campana?.tiene_adjunto && <Adjunto campanaId={campana.id} compacto />}
          {texto || <span style={{ color: '#9ca3af' }}>Tu mensaje aparecerá aquí</span>}
        </div>
      </div>
    </div>
  )
}

export default function FormularioCampana({ campana, onCerrar, onGuardada }) {
  const editando = Boolean(campana)
  const [nombre, setNombre] = useState(campana?.nombre || '')
  const [mensaje, setMensaje] = useState(campana?.mensaje || '')
  const [etiquetas, setEtiquetas] = useState(campana?.etiquetas || [])
  const [archivo, setArchivo] = useState(null)
  const [error, setError] = useState('')
  const [guardando, setGuardando] = useState(false)
  const areaMensaje = useRef(null)
  const entradaArchivo = useRef(null)

  const insertarNombre = () => {
    const area = areaMensaje.current
    const inicio = area?.selectionStart ?? mensaje.length
    const fin = area?.selectionEnd ?? mensaje.length
    setMensaje(mensaje.slice(0, inicio) + '{{nombre}}' + mensaje.slice(fin))
    requestAnimationFrame(() => { area?.focus(); area?.setSelectionRange(inicio + 10, inicio + 10) })
  }

  const elegirArchivo = e => {
    const elegido = e.target.files[0]
    e.target.value = ''
    if (!elegido) return
    const problema = revisarAdjunto(elegido)
    if (problema) { setError(problema); return }
    setError('')
    setArchivo(elegido)
  }

  const guardar = async e => {
    e.preventDefault()
    setError('')
    if (!nombre.trim() || !mensaje.trim()) {
      setError('El nombre y el mensaje son obligatorios.')
      return
    }
    setGuardando(true)
    let guardada = null
    try {
      guardada = editando
        ? await editarCampana(campana.id, { nombre, mensaje, etiquetas })
        : await crearCampana({ nombre, mensaje, etiquetas })
      if (archivo) guardada = await subirAdjunto(guardada.id, archivo)
      sileo.success({
        title: editando ? 'Campaña actualizada' : 'Campaña creada',
        description: `${guardada.destinatarios} destinatarios`,
      })
      onGuardada(guardada)
    } catch (err) {
      // Si la campana se creo pero el adjunto fallo, se abre en edicion para reintentar.
      if (guardada && !editando) {
        sileo.error({ title: 'La campaña se guardó, pero el adjunto no', description: err.mensajeUsuario })
        onGuardada(guardada, { reabrir: true })
        return
      }
      setError(err.mensajeUsuario)
      setGuardando(false)
    }
  }

  return (
    <Modal titulo={editando ? 'Editar campaña' : 'Nueva campaña'} onCerrar={onCerrar} ancho={820}>
      <form onSubmit={guardar} className="formulario-campana">
        <div>
          <FormField label="Nombre de la campaña" value={nombre} onChange={setNombre} placeholder="Promoción de noviembre" autoFocus maxLength={150} />
          <div className="campo">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
              <label>Mensaje</label>
              <button type="button" className="boton-enlace" onClick={insertarNombre}>Insertar {'{{nombre}}'}</button>
            </div>
            <textarea
              ref={areaMensaje}
              className="entrada"
              rows={7}
              value={mensaje}
              maxLength={MAX_MENSAJE}
              onChange={e => setMensaje(e.target.value)}
              placeholder="Hola {{nombre}}, tenemos una oferta para ti..."
              style={{ resize: 'vertical', lineHeight: 1.5 }}
            />
            <p className="texto-suave" style={{ fontSize: '0.74rem', marginTop: 4, textAlign: 'right' }}>{mensaje.length} / {MAX_MENSAJE}</p>
          </div>
          <SelectorEtiquetas elegidas={etiquetas} onCambiar={setEtiquetas} />
          <div className="campo">
            <label>Imagen o video (opcional)</label>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
              <button type="button" className="boton boton-secundario" style={{ padding: '7px 14px', fontSize: '0.82rem' }} onClick={() => entradaArchivo.current?.click()}>
                {archivo || campana?.tiene_adjunto ? 'Cambiar archivo' : 'Elegir archivo'}
              </button>
              <span className="texto-suave" style={{ fontSize: '0.78rem' }}>
                {archivo ? archivo.name : campana?.tiene_adjunto ? 'Ya tiene un archivo adjunto' : 'JPG, PNG o WEBP hasta 5 MB, MP4 hasta 16 MB'}
              </span>
              {archivo && <button type="button" className="boton-enlace peligro" onClick={() => setArchivo(null)}>Quitar</button>}
            </div>
            <input ref={entradaArchivo} type="file" accept={ACEPTA_ADJUNTO} style={{ display: 'none' }} onChange={elegirArchivo} />
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <VistaPreviaMensaje mensaje={mensaje} archivo={archivo} campana={campana} />
          <AlertBox>{error}</AlertBox>
          <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 'auto' }}>
            <button type="button" className="boton boton-secundario" onClick={onCerrar}>Cancelar</button>
            <button type="submit" className="boton boton-primario" disabled={guardando}>
              {guardando ? 'Guardando...' : editando ? 'Guardar cambios' : 'Crear campaña'}
            </button>
          </div>
        </div>
      </form>
    </Modal>
  )
}
