from ..utils.text import escape_html, text_to_html


def create_custom_message_email(*, title: str, message: str, signature: str) -> dict:
    safe_title = escape_html(title)
    safe_message = text_to_html(message)
    safe_signature = escape_html(signature or "MassSend")

    text = "\n".join([title, "", message, "", signature or "MassSend"])

    html = f"""
    <!DOCTYPE html>
    <html lang="es">
      <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{safe_title}</title>
      </head>
      <body style="margin:0;padding:0;background:#eef2f7;font-family:Arial,Helvetica,sans-serif;color:#1f2937;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#eef2f7;">
          <tr>
            <td align="center" style="padding:34px 14px;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width:620px;background:#ffffff;border-radius:14px;overflow:hidden;box-shadow:0 6px 20px rgba(15,23,42,.10);">
                <tr>
                  <td style="height:8px;background:#128c4a;font-size:0;line-height:0;">&nbsp;</td>
                </tr>
                <tr>
                  <td style="padding:34px 34px 18px;">
                    <p style="margin:0 0 10px;color:#128c4a;font-size:12px;font-weight:700;letter-spacing:1.4px;text-transform:uppercase;">Notificación</p>
                    <h1 style="margin:0;color:#0f172a;font-size:26px;line-height:1.3;">{safe_title}</h1>
                  </td>
                </tr>
                <tr>
                  <td style="padding:0 34px 30px;">
                    <div style="padding:22px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;">
                      <p style="margin:0;color:#334155;font-size:15px;line-height:1.8;">{safe_message}</p>
                    </div>
                  </td>
                </tr>
                <tr>
                  <td style="padding:22px 34px;background:#0f172a;">
                    <p style="margin:0;color:#ffffff;font-size:13px;font-weight:700;">{safe_signature}</p>
                    <p style="margin:6px 0 0;color:#cbd5e1;font-size:12px;">Correo generado desde MassSend.</p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        </table>
      </body>
    </html>
    """

    return {"text": text, "html": html}
