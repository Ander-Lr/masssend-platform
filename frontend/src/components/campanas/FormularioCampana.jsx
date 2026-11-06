import { useEffect, useRef, useState } from 'react'
import { sileo } from 'sileo'
import AlertBox from '../auth/AlertBox'
import FormField from '../auth/FormField'
import Modal from '../ui/Modal'
import { etiquetas as pedirEtiquetas } from '../../api/contactos'
import {
  ACEPTA_ADJUNTO, MAX_MENSAJE, crearCampana, editarCampana, personalizar, revisarAdjunto, subirAdjunto,
} from '../../api/campanas'
import Adjunto, { ArchivoPendiente } from './Adjunto'
import Boton, { BotonEnlace } from '../ui/Boton'
import { Etiqueta, claseEntrada } from '../ui/Campo'
import { claseEnlace } from '../ui/clases'

// Etiquetas elegidas con un clic entre las que ya existen en los contactos.
function SelectorEtiquetas({ elegidas, onCambiar }) {
  const [disponibles, setDisponibles] = useState([])
  useEffect(() => { pedirEtiquetas().then(r => setDisponibles(r.datos)).catch(() => {}) }, [])
  const alternar = e => onCambiar(elegidas.includes(e) ? elegidas.filter(x => x !== e) : [...elegidas, e])

  return (
    <div className="mb-4">
      <Etiqueta>Destinatarios</Etiqueta>
      {disponibles.length === 0 ? (
        <p className="text-[0.8rem] text-gray-500">Tus contactos no tienen etiquetas: la campaña irá a todos los contactos activos.</p>
      ) : (
        <>
          <div className="flex flex-wrap gap-1.5">
            {disponibles.map(e => (
              <button type="button" key={e} className={`rounded-full border-[1.5px] px-3 py-1 text-[0.78rem] transition-colors ${elegidas.includes(e) ? 'border-violet-600 bg-violet-600 text-white' : 'border-purple-200 bg-white text-violet-600 hover:border-violet-400'}`} onClick={() => alternar(e)}>{e}</button>
            ))}
          </div>
          <p className="mt-1.5 text-[0.76rem] text-gray-500">
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
    <div className="min-h-[220px] rounded-xl bg-chat p-4">
      <p className="mb-2 text-[0.72rem] font-bold uppercase tracking-wide text-whatsapp">Vista previa para un contacto llamado Juan</p>
      <div className="flex justify-end">
        <div className="max-w-[90%] whitespace-pre-wrap break-words rounded-lg rounded-br-sm bg-burbuja px-3 py-2 text-[0.88rem] leading-snug">
          {archivo
            ? <ArchivoPendiente>{archivo.name}</ArchivoPendiente>
            : campana?.tiene_adjunto && <Adjunto campanaId={campana.id} compacto />}
          {texto || <span className="text-gray-400">Tu mensaje aparecerá aquí</span>}
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
    <Modal titulo={editando ? 'Editar campaña' : 'Nueva campaña'} onCerrar={onCerrar} ancho="max-w-[820px]">
      <form onSubmit={guardar} className="grid gap-6 md:grid-cols-[1.2fr_1fr]">
        <div>
          <FormField label="Nombre de la campaña" value={nombre} onChange={setNombre} placeholder="Promoción de noviembre" autoFocus maxLength={150} />
          <div className="mb-4">
            <div className="flex items-baseline justify-between">
              <Etiqueta>Mensaje</Etiqueta>
              <button type="button" className={claseEnlace} onClick={insertarNombre}>Insertar {'{{nombre}}'}</button>
            </div>
            <textarea
              ref={areaMensaje}
              className={`${claseEntrada} resize-y leading-normal`}
              rows={7}
              value={mensaje}
              maxLength={MAX_MENSAJE}
              onChange={e => setMensaje(e.target.value)}
              placeholder="Hola {{nombre}}, tenemos una oferta para ti..."
            />
            <p className="mt-1 text-right text-[0.74rem] text-gray-500">{mensaje.length} / {MAX_MENSAJE}</p>
          </div>
          <SelectorEtiquetas elegidas={etiquetas} onCambiar={setEtiquetas} />
          <div className="mb-4">
            <Etiqueta>Imagen o video (opcional)</Etiqueta>
            <div className="flex flex-wrap items-center gap-2.5">
              <Boton variante="secundario" tamano="sm" onClick={() => entradaArchivo.current?.click()}>
                {archivo || campana?.tiene_adjunto ? 'Cambiar archivo' : 'Elegir archivo'}
              </Boton>
              <span className="text-[0.78rem] text-gray-500">
                {archivo ? archivo.name : campana?.tiene_adjunto ? 'Ya tiene un archivo adjunto' : 'JPG, PNG o WEBP hasta 5 MB, MP4 hasta 16 MB'}
              </span>
              {archivo && <BotonEnlace peligro onClick={() => setArchivo(null)}>Quitar</BotonEnlace>}
            </div>
            <input ref={entradaArchivo} type="file" accept={ACEPTA_ADJUNTO} className="hidden" onChange={elegirArchivo} />
          </div>
        </div>

        <div className="flex flex-col gap-3.5">
          <VistaPreviaMensaje mensaje={mensaje} archivo={archivo} campana={campana} />
          <AlertBox>{error}</AlertBox>
          <div className="mt-auto flex justify-end gap-2.5">
            <Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton>
            <Boton type="submit" disabled={guardando}>
              {guardando ? 'Guardando...' : editando ? 'Guardar cambios' : 'Crear campaña'}
            </Boton>
          </div>
        </div>
      </form>
    </Modal>
  )
}
