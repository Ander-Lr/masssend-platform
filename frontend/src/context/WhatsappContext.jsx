import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { estadoWhatsapp } from '../api/envio'
import { useAuth } from './AuthContext'

const WhatsappContext = createContext({ conectado: null })
const INTERVALO_MS = 10000

// Estado del numero de la plataforma, compartido por el menu y las paginas.
// Solo staff puede consultarlo: para los demas queda en null.
export function WhatsappProvider({ children }) {
  const { usuario } = useAuth()
  const [estado, setEstado] = useState({ conectado: null, codigo_vinculacion: null })
  const esStaff = Boolean(usuario?.es_staff)

  const actualizar = useCallback(() => estadoWhatsapp().then(setEstado).catch(() => {}), [])

  useEffect(() => {
    if (!esStaff) return undefined
    let vigente = true
    const consultar = () => estadoWhatsapp().then(e => vigente && setEstado(e)).catch(() => {})
    consultar()
    const t = setInterval(consultar, INTERVALO_MS)
    return () => { vigente = false; clearInterval(t) }
  }, [esStaff])

  return (
    <WhatsappContext.Provider value={{ ...estado, conectado: esStaff ? estado.conectado : null, actualizar, setEstado }}>
      {children}
    </WhatsappContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export const useWhatsapp = () => useContext(WhatsappContext)
