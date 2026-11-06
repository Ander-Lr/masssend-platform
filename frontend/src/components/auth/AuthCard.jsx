// Envoltorio visual de todas las pantallas sin sesion. Solo layout y estilo.
export default function AuthCard({ title, subtitle, children, ancho = 'w-[380px]' }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-lienzo p-4">
      <div className={`max-w-full rounded-2xl bg-white px-9 py-10 shadow-[0_4px_24px_rgba(0,0,0,0.08)] ${ancho}`}>
        <div className="mb-7 text-center">
          <h1 className="text-[1.6rem] font-extrabold text-tinta">Mass<span className="text-marca">Send</span></h1>
          {title && <p className="mt-3.5 text-base font-bold text-gray-700">{title}</p>}
          {subtitle && <p className="mt-1.5 text-[0.82rem] leading-normal text-gray-400">{subtitle}</p>}
        </div>
        {children}
      </div>
    </div>
  )
}
