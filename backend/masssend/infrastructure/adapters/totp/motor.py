import base64
import hmac
from datetime import datetime
from io import BytesIO

import pyotp
import qrcode

PERIODO = 30


class TotpPyotp:
    def __init__(self, emisor: str, ventana: int) -> None:
        self._emisor = emisor
        self._ventana = ventana

    def generar_secreto(self) -> str:
        return pyotp.random_base32()

    def uri(self, secreto: str, correo: str) -> str:
        return pyotp.TOTP(secreto).provisioning_uri(name=correo, issuer_name=self._emisor)

    def qr(self, uri: str) -> str:
        imagen = qrcode.make(uri)
        memoria = BytesIO()
        imagen.save(memoria, format="PNG")
        return f"data:image/png;base64,{base64.b64encode(memoria.getvalue()).decode('ascii')}"

    def paso_valido(self, secreto: str, codigo: str, ahora: datetime) -> int | None:
        limpio = codigo.replace(" ", "")
        if not secreto or len(limpio) != 6 or not limpio.isdigit():
            return None
        motor = pyotp.TOTP(secreto)
        paso_actual = int(ahora.timestamp()) // PERIODO
        for paso in range(paso_actual - self._ventana, paso_actual + self._ventana + 1):
            if hmac.compare_digest(motor.at(paso * PERIODO), limpio):
                return paso
        return None
