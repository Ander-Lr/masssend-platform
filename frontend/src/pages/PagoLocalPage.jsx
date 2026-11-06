import { useEffect, useState } from 'react'
import AuthCard from '../components/auth/AuthCard'
import AlertBox from '../components/auth/AlertBox'
import FormField from '../components/auth/FormField'
import PrimaryButton from '../components/auth/PrimaryButton'
import { claseBoton } from '../components/ui/clases'

// PayPhone solo abre su formulario si el navegador llega desde el dominio registrado.
// Postman usa /?pagar=<url_pago> para abrirlo desde aqui. Solo se aceptan pasarelas conocidas.
const DESTINOS = ['pay.payphonetodoesposible.com', 'payp.page.link', 'www.sandbox.paypal.com', 'www.paypal.com']

const destinoPermitido = valor => {
  try {
    const url = new URL(valor)
    return url.protocol === 'https:' && DESTINOS.includes(url.hostname) ? url.href : null
  } catch {
    return null
  }
}

export default function PagoLocalPage({ url }) {
  const destino = destinoPermitido(url)
  const [pegada, setPegada] = useState('')

  useEffect(() => {
    if (!destino) return undefined
    const t = setTimeout(() => window.location.assign(destino), 800)
    return () => clearTimeout(t)
  }, [destino])

  if (destino) {
    return (
      <AuthCard title="Abriendo el formulario de pago..." subtitle="Si no se abre solo, usa el botón.">
        <a href={destino} className={claseBoton({ bloque: true })}>Ir a pagar</a>
      </AuthCard>
    )
  }

  return (
    <AuthCard title="Pagos locales" subtitle="Pega el url_pago del checkout para abrirlo desde este dominio.">
      {url && <AlertBox>La URL de pago no es válida o no pertenece a una pasarela conocida.</AlertBox>}
      <form onSubmit={e => { e.preventDefault(); window.location.assign(`/?pagar=${encodeURIComponent(pegada.trim())}`) }}>
        <FormField label="URL de pago" type="url" value={pegada} onChange={setPegada} placeholder="https://pay.payphonetodoesposible.com/..." autoFocus />
        <PrimaryButton>Ir a pagar</PrimaryButton>
      </form>
    </AuthCard>
  )
}
