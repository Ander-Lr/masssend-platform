import { useEffect, useState } from 'react'
import { descargarAdjunto } from '../../api/campanas'

// El adjunto se pide con el JWT y se muestra desde una URL local del navegador.
export default function Adjunto({ campanaId, compacto = false }) {
  const [archivo, setArchivo] = useState(null)
  const [fallo, setFallo] = useState(false)

  useEffect(() => {
    let url = ''
    let vigente = true
    descargarAdjunto(campanaId)
      .then(blob => {
        if (!vigente) return
        url = URL.createObjectURL(blob)
        setArchivo({ url, video: blob.type.startsWith('video/') })
      })
      .catch(() => vigente && setFallo(true))
    return () => {
      vigente = false
      if (url) URL.revokeObjectURL(url)
    }
  }, [campanaId])

  if (fallo) return <div className="adjunto-nuevo">No se pudo cargar el adjunto</div>
  if (!archivo) return <div className="adjunto-nuevo">Cargando adjunto...</div>
  const estilo = { display: 'block', maxWidth: '100%', maxHeight: compacto ? 180 : 320, borderRadius: 6, marginBottom: 6 }
  return archivo.video
    ? <video src={archivo.url} controls style={estilo} />
    : <img src={archivo.url} alt="Adjunto de la campaña" style={estilo} />
}
