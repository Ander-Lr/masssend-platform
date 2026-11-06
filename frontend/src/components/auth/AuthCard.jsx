// Envoltorio visual de todas las pantallas sin sesion. Solo layout y estilo.
export default function AuthCard({ title, subtitle, children, width = 380 }) {
  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center',
      justifyContent: 'center', background: '#f0f2f5', padding: 16,
    }}>
      <div style={{
        background: '#fff', borderRadius: 16, padding: '40px 36px',
        width, maxWidth: '100%', boxShadow: '0 4px 24px rgba(0,0,0,0.08)',
      }}>
        <div style={{ textAlign: 'center', marginBottom: 28 }}>
          <h1 style={{ fontSize: '1.6rem', fontWeight: 800, color: '#1a1a2e', margin: 0 }}>
            Mass<span style={{ color: '#25d366' }}>Send</span>
          </h1>
          {title && (
            <p style={{ color: '#374151', fontSize: '1rem', fontWeight: 700, marginTop: 14 }}>{title}</p>
          )}
          {subtitle && (
            <p style={{ color: '#888', fontSize: '0.82rem', marginTop: 6, lineHeight: 1.5 }}>{subtitle}</p>
          )}
        </div>
        {children}
      </div>
    </div>
  )
}
