from ..utils.text import escape_html


def create_verification_email(*, name: str, code: str, expiration_minutes: int) -> dict:
    safe_name = escape_html(name)
    safe_code = escape_html(code)
    expiration_text = f"{expiration_minutes} minuto(s)"

    subject = f"{code} es tu código de activación · MassSend"

    text = "\n".join([
        f"Hola {name}:",
        "",
        "Se solicitó la activación de una cuenta de MassSend con este correo.",
        f"Código de verificación: {code}",
        f"El código vence en {expiration_text}.",
        "",
        "Si tú no realizaste este registro, puedes ignorar este mensaje.",
        "",
        "MassSend",
    ])

    html = f"""
    <!DOCTYPE html>
    <html lang="es">
      <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Activación de cuenta</title>
      </head>
      <body style="margin:0;padding:0;background:#f0f2f5;font-family:Arial,Helvetica,sans-serif;color:#1f2937;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#f0f2f5;">
          <tr>
            <td align="center" style="padding:32px 14px;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width:600px;background:#ffffff;border-radius:14px;overflow:hidden;box-shadow:0 6px 20px rgba(15,23,42,.10);">
                <tr>
                  <td align="center" style="padding:30px 24px;background:#128c4a;">
                    <div style="width:58px;height:58px;line-height:58px;margin:0 auto 14px;border-radius:50%;background:#ffffff;color:#128c4a;font-size:22px;font-weight:800;text-align:center;">MS</div>
                    <h1 style="margin:0;color:#ffffff;font-size:24px;">Activación de cuenta</h1>
                    <p style="margin:8px 0 0;color:#dcfce7;font-size:14px;">Mass<strong>Send</strong> · Sistema de Mensajería</p>
                  </td>
                </tr>
                <tr>
                  <td style="padding:34px 34px 22px;">
                    <p style="margin:0 0 18px;font-size:17px;line-height:1.6;">Hola <strong>{safe_name}</strong>:</p>
                    <p style="margin:0 0 22px;font-size:15px;line-height:1.7;color:#475569;">Se solicitó la activación de una cuenta utilizando este correo electrónico. Ingresa el siguiente código en la aplicación:</p>
                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                      <tr>
                        <td align="center" style="padding:24px 12px;background:#ecfdf5;border:1px solid #a7f3d0;border-radius:12px;">
                          <p style="margin:0 0 8px;color:#475569;font-size:12px;font-weight:700;letter-spacing:1.4px;text-transform:uppercase;">Código de verificación</p>
                          <p style="margin:0;color:#128c4a;font-size:38px;font-weight:700;letter-spacing:9px;line-height:1.3;">{safe_code}</p>
                        </td>
                      </tr>
                    </table>
                    <div style="margin-top:22px;padding:14px 16px;background:#fff7ed;border-left:4px solid #f97316;border-radius:6px;">
                      <p style="margin:0;color:#9a3412;font-size:14px;line-height:1.5;">Este código vence en <strong>{expiration_text}</strong>.</p>
                    </div>
                    <p style="margin:24px 0 0;font-size:14px;line-height:1.7;color:#64748b;">Por seguridad, no compartas este código. La cuenta permanecerá inactiva hasta que el código sea validado.</p>
                  </td>
                </tr>
                <tr>
                  <td align="center" style="padding:22px;background:#f8fafc;border-top:1px solid #e2e8f0;">
                    <p style="margin:0 0 5px;color:#334155;font-size:13px;font-weight:700;">MassSend</p>
                    <p style="margin:0;color:#94a3b8;font-size:12px;">Mensaje automático. No respondas a este correo.</p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        </table>
      </body>
    </html>
    """

    return {"subject": subject, "text": text, "html": html}
