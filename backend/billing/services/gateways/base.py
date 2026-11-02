"""
Contrato común para cualquier pasarela de pago. checkout_service.py
solo conoce esta interfaz (principio de inversión de dependencias):
agregar una tercera pasarela el día de mañana significa escribir una
clase nueva acá, sin tocar el resto del módulo.
"""
from abc import ABC, abstractmethod


class PaymentGateway(ABC):
    name = None  # "PAYPAL" | "PAYPHONE" (debe matchear PaymentTransaction.PROVIDER_CHOICES)

    @abstractmethod
    def create_payment(self, *, pack, reference_hint: str) -> dict:
        """
        Inicia el cobro en la pasarela. Debe devolver:
        {"provider_reference": str, "redirect_url": str, "raw": dict}
        """
        raise NotImplementedError

    @abstractmethod
    def confirm_payment(self, *, provider_reference: str, extra: dict) -> dict:
        """
        Confirma contra la API real del proveedor si el pago se
        completó. Debe devolver: {"approved": bool, "raw": dict}
        """
        raise NotImplementedError
