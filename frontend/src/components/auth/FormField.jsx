export default function FormField({
  label, type = 'text', value, onChange, required = true, placeholder, autoFocus,
  autoComplete, inputMode, maxLength, codigo = false, ayuda,
}) {
  return (
    <div className="campo">
      <label>{label}</label>
      <input
        className={`entrada${codigo ? ' entrada-codigo' : ''}`}
        type={type}
        value={value}
        onChange={e => onChange(e.target.value)}
        required={required}
        placeholder={placeholder}
        autoFocus={autoFocus}
        autoComplete={autoComplete}
        inputMode={inputMode}
        maxLength={maxLength}
      />
      {ayuda && <p className="texto-suave" style={{ fontSize: '0.76rem', marginTop: 6 }}>{ayuda}</p>}
    </div>
  )
}

// Campo de 6 digitos para codigos de correo y del autenticador.
export function CodigoField({ label = 'Código', value, onChange, autoFocus = true }) {
  return (
    <FormField
      label={label}
      value={value}
      onChange={v => onChange(v.replace(/\D/g, '').slice(0, 6))}
      placeholder="000000"
      inputMode="numeric"
      autoComplete="one-time-code"
      maxLength={6}
      autoFocus={autoFocus}
      codigo
    />
  )
}
