import { useEffect, useState } from 'react'
import { descargarAdjunto } from '../../api/campanas'

export function ArchivoPendiente({ children }) {
  return <div className="mb-1.5 rounded-md bg-black/5 px-2.5 py-2 text-[0.78rem] text-gray-700">{children}</div>
}

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

  if (fallo) return <ArchivoPendiente>No se pudo cargar el adjunto</ArchivoPendiente>
  if (!archivo) return <ArchivoPendiente>Cargando adjunto...</ArchivoPendiente>
  const clase = `mb-1.5 block max-w-full rounded-md ${compacto ? 'max-h-[180px]' : 'max-h-80'}`
  return archivo.video
    ? <video src={archivo.url} controls className={clase} />
    : <img src={archivo.url} alt="Adjunto de la campaña" className={clase} />
}
