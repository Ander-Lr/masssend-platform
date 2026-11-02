"""Envuelve las pasarelas actuales de billing, sin reescribirlas."""

import logging
from collections.abc import Callable
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace
from typing import Any

import requests

from billing.services.gateways.base import PaymentGateway
from billing.services.gateways.paypal_gateway import PayPalGateway
from billing.services.gateways.payphone_gateway import PayPhoneGateway
from billing.utils.errors import AppError
from masssend.application.creditos.puertos import CobroConfirmado, CobroIniciado, Paquete
from masssend.domain.shared.dinero import Dinero
from masssend.domain.shared.errores import DatosInvalidos, ServicioNoDisponible

logger = logging.getLogger(__name__)
NO_DISPONIBLE = "La pasarela de pago no está disponible."


def monto_paypal(respuesta: dict[str, Any]) -> Dinero | None:
    try:
        captura = respuesta["purchase_units"][0]["payments"]["captures"][0]["amount"]
        return Dinero.desde_decimal(captura["value"], captura["currency_code"])
    except (KeyError, IndexError, TypeError, DatosInvalidos):
        return None


def monto_payphone(respuesta: dict[str, Any]) -> Dinero | None:
    try:
        return Dinero(int(Decimal(str(respuesta["amount"]))))
    except (KeyError, InvalidOperation, ValueError, DatosInvalidos):
        return None


class PasarelaHeredada:
    def __init__(
        self,
        pasarela: PaymentGateway,
        leer_monto: Callable[[dict[str, Any]], Dinero | None],
    ) -> None:
        self._pasarela = pasarela
        self._leer_monto = leer_monto
        self.nombre: str = pasarela.name or ""

    def iniciar(self, paquete: Paquete, referencia: str) -> CobroIniciado:
        paquete_actual = SimpleNamespace(
            id=paquete.id,
            name=paquete.nombre,
            credits=paquete.creditos,
            price_usd=paquete.precio.como_decimal(),
        )
        resultado = self._llamar(
            lambda: self._pasarela.create_payment(
                pack=paquete_actual, reference_hint=referencia
            )
        )
        return CobroIniciado(
            resultado["provider_reference"],
            resultado.get("redirect_url"),
            resultado.get("raw", {}),
        )

    def confirmar(self, referencia: str, datos: dict[str, object]) -> CobroConfirmado:
        resultado = self._llamar(
            lambda: self._pasarela.confirm_payment(provider_reference=referencia, extra=datos)
        )
        respuesta = resultado.get("raw") or {}
        return CobroConfirmado(
            bool(resultado.get("approved")), self._leer_monto(respuesta), respuesta
        )

    def _llamar(self, accion: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        try:
            return accion()
        except AppError as error:
            raise DatosInvalidos(error.message, "datos_pasarela") from error
        except (requests.RequestException, KeyError, TypeError, ValueError) as error:
            logger.warning("%s no respondio: %s", self.nombre, type(error).__name__)
            raise ServicioNoDisponible(NO_DISPONIBLE) from error


def paypal() -> PasarelaHeredada:
    return PasarelaHeredada(PayPalGateway(), monto_paypal)


def payphone() -> PasarelaHeredada:
    return PasarelaHeredada(PayPhoneGateway(), monto_payphone)
