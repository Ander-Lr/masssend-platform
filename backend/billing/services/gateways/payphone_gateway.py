"""
PayPhone Payment Links (Ecuador, sandbox). Adaptado de
`pasarela-mensajes-node/src/services/payphone.service.js` (POST
/api/Links con amount en centavos), agregando la confirmación real
del pago vía /api/button/V2/Confirm.

⚠️ Nota honesta: la práctica original solo cubre "crear el link"
(nunca confirma el pago). El paso de confirmación aquí sigue la API
pública V2 de PayPhone (Confirm recibe {id, clientTransactionId} y
responde con el estado de la transacción), pero no pude probarlo
contra su sandbox real en esta sesión (sin acceso a internet desde
aquí). Si al probarlo el nombre de algún campo no calza, es el primer
lugar a revisar.
"""
import requests
from django.conf import settings

from .base import PaymentGateway
from ...utils.errors import AppError


def _generate_client_transaction_id() -> str:
    import time
    base = format(int(time.time() * 1000), "x").upper()
    return f"TX{base}"[:15]


def _clean_text(value: str, max_length: int) -> str:
    import re
    return re.sub(r"[^\w\sÁÉÍÓÚáéíóúÑñ.,:-]", "", value or "")[:max_length]


class PayPhoneGateway(PaymentGateway):
    name = "PAYPHONE"

    def create_payment(self, *, pack, reference_hint: str) -> dict:
        client_transaction_id = _generate_client_transaction_id()
        amount_cents = int(round(pack.price_usd * 100))

        if amount_cents <= 0:
            raise AppError("El monto del paquete debe ser mayor a cero.", 400)

        body = {
            "amount": amount_cents,
            "amountWithoutTax": amount_cents,
            "clientTransactionId": client_transaction_id,
            "currency": "USD",
            "reference": _clean_text(f"MassSend - {pack.name}", 100),
        }

        response = requests.post(
            f"{settings.PAYPHONE_BASE_URL}/api/Links",
            json=body,
            headers={
                "Authorization": f"Bearer {settings.PAYPHONE_TOKEN}",
                "Content-Type": "application/json",
            },
            timeout=15,
        )
        response.raise_for_status()

        # El endpoint /api/Links de PayPhone responde con la URL de
        # pago directamente (texto plano) o, según la cuenta, un JSON
        # con el link adentro. Se contemplan ambos casos.
        try:
            data = response.json()
            redirect_url = data if isinstance(data, str) else data.get("payWithPayPhone") or data.get("url")
        except ValueError:
            redirect_url = response.text.strip().strip('"')
            data = {"raw_text": response.text}

        return {
            "provider_reference": client_transaction_id,
            "redirect_url": redirect_url,
            "raw": data,
        }

    def confirm_payment(self, *, provider_reference: str, extra: dict) -> dict:
        transaction_id = (extra or {}).get("id")
        if not transaction_id:
            raise AppError(
                "Falta el parámetro 'id' que PayPhone debe enviar al volver del pago.", 400,
            )

        response = requests.post(
            f"{settings.PAYPHONE_BASE_URL}/api/button/V2/Confirm",
            json={"id": int(transaction_id), "clientTransactionId": provider_reference},
            headers={
                "Authorization": f"Bearer {settings.PAYPHONE_TOKEN}",
                "Content-Type": "application/json",
            },
            timeout=15,
        )
        response.raise_for_status()
        result = response.json()

        status_text = str(result.get("transactionStatus", "")).upper()
        approved = status_text == "APPROVED" or result.get("statusCode") == 3

        return {"approved": approved, "raw": result}
