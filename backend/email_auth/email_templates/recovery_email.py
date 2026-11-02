from ..utils.text import escape_html


def create_recovery_email(*, name: str, reset_url: str, expiration_minutes: int) -> dict:
    """
    A diferencia del OTP, aquí no se envía un código para copiar: se
    envía un enlace con un token temporal. El usuario hace clic y el
    frontend valida ese token antes de permitir el cambio de clave.
    """
    safe_name = escape_html(name)
    expiration_text = f"{expiration_minutes} minuto(s)"

    subject = "Recuperación de tu cuenta · MassSend"

    text = "\n".join([
        f"Hola {name}:",
        "",
        "Se solicitó la recuperación de esta cuenta de MassSend.",
        f"Ingresa al siguiente enlace para continuar: {reset_url}",
        f"El enlace vence en {expiration_text}.",
        "",
        "Si tú no solicitaste este cambio, puedes ignorar este mensaje.",
        "",
        "MassSend",
    ])

    html = f"""
    <!DOCTYPE html>
    <html lang="es">
      <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Recuperación de cuenta</title>
      </head>
      <body style="margin:0;padding:0;background:#f0f2f5;font-family:Arial,Helvetica,sans-serif;color:#1f2937;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#f0f2f5;">
          <tr>
            <td align="center" style="padding:32px 14px;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width:600px;background:#ffffff;border-radius:14px;overflow:hidden;box-shadow:0 6px 20px rgba(15,23,42,.10);">
                <tr>
                  <td align="center" style="padding:30px 24px;background:#172554;">
                    <div style="width:58px;height:58px;line-height:58px;margin:0 auto 14px;border-radius:50%;background:#ffffff;color:#172554;font-size:22px;font-weight:800;text-align:center;">MS</div>
                    <h1 style="margin:0;color:#ffffff;font-size:24px;">Recuperación de cuenta</h1>
                    <p style="margin:8px 0 0;color:#dbeafe;font-size:14px;">MassSend</p>
                  </td>
                </tr>
                <tr>
                  <td style="padding:34px 34px 22px;">
                    <p style="margin:0 0 18px;font-size:17px;line-height:1.6;">Hola <strong>{safe_name}</strong>:</p>
                    <p style="margin:0 0 22px;font-size:15px;line-height:1.7;color:#475569;">Se solicitó la recuperación de esta cuenta. Haz clic en el siguiente botón para continuar:</p>
                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                      <tr>
                        <td align="center" style="padding:10px 12px 26px;">
                          <a href="{reset_url}" style="display:inline-block;padding:14px 32px;background:#128c4a;color:#ffffff;text-decoration:none;font-weight:700;font-size:15px;border-radius:8px;">Recuperar mi cuenta</a>
                        </td>
                      </tr>
                    </table>
                    <div style="margin-top:6px;padding:14px 16px;background:#fff7ed;border-left:4px solid #f97316;border-radius:6px;">
                      <p style="margin:0;color:#9a3412;font-size:14px;line-height:1.5;">Este enlace vence en <strong>{expiration_text}</strong> y solo puede usarse una vez.</p>
                    </div>
                    <p style="margin:24px 0 0;font-size:14px;line-height:1.7;color:#64748b;">Si el botón no funciona, copia y pega esta dirección en tu navegador:</p>
                    <p style="margin:6px 0 0;font-size:13px;line-height:1.6;color:#128c4a;word-break:break-all;">{reset_url}</p>
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
