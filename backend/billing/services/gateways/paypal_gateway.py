"""
PayPal Orders API v2 (checkout de una sola vez, sandbox). Adaptado de
`pasarela-mensajes-node/src/services/paypal.service.js`: mismo flujo
(oauth2/token -> crear orden -> capturar orden), reescrito para Django
y agregando `application_context` con return_url/cancel_url para que
PayPal redirija de vuelta al frontend después de pagar (la práctica
original no lo tenía porque no usaba redirección real).
"""
import requests
from django.conf import settings

from .base import PaymentGateway


class PayPalGateway(PaymentGateway):
    name = "PAYPAL"

    def _basic_auth(self) -> str:
        import base64
        credentials = f"{settings.PAYPAL_CLIENT_ID}:{settings.PAYPAL_CLIENT_SECRET}"
        return base64.b64encode(credentials.encode()).decode()

    def _get_access_token(self) -> str:
        response = requests.post(
            f"{settings.PAYPAL_BASE_URL}/v1/oauth2/token",
            data="grant_type=client_credentials",
            headers={
                "Authorization": f"Basic {self._basic_auth()}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            timeout=15,
        )
        response.raise_for_status()
        return response.json()["access_token"]

    def create_payment(self, *, pack, reference_hint: str) -> dict:
        token = self._get_access_token()

        body = {
            "intent": "CAPTURE",
            "purchase_units": [{
                "amount": {"currency_code": "USD", "value": f"{pack.price_usd:.2f}"},
                "description": f"MassSend - {pack.name} ({pack.credits} créditos)",
                "custom_id": reference_hint,
            }],
            "application_context": {
                "brand_name": "MassSend",
                "user_action": "PAY_NOW",
                "return_url": f"{settings.FRONTEND_URL}/billing/return?provider=paypal",
                "cancel_url": f"{settings.FRONTEND_URL}/billing/return?provider=paypal&cancelled=1",
            },
        }

        response = requests.post(
            f"{settings.PAYPAL_BASE_URL}/v2/checkout/orders",
            json=body,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=15,
        )
        response.raise_for_status()
        order = response.json()

        approve_link = next(
            (link["href"] for link in order.get("links", []) if link.get("rel") == "approve"),
            None,
        )

        return {
            "provider_reference": order["id"],
            "redirect_url": approve_link,
            "raw": order,
        }

    def confirm_payment(self, *, provider_reference: str, extra: dict) -> dict:
        token = self._get_access_token()

        response = requests.post(
            f"{settings.PAYPAL_BASE_URL}/v2/checkout/orders/{provider_reference}/capture",
            json={},
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=15,
        )
        # PayPal responde 201 en éxito; si ya se había capturado antes
        # devuelve 422 UNPROCESSABLE_ENTITY con status COMPLETED igual.
        try:
            capture = response.json()
        except ValueError:
            response.raise_for_status()
            raise

        approved = capture.get("status") == "COMPLETED"
        return {"approved": approved, "raw": capture}
