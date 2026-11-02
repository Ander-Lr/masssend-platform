import uuid

from django.conf import settings
from django.db import models


class CreditWallet(models.Model):
    """Saldo de créditos de un usuario. 1 crédito = 1 mensaje de campaña enviado."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="credit_wallet",
    )
    balance = models.PositiveIntegerField(default=0, verbose_name="Saldo de créditos")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "billing_credit_wallet"
        verbose_name = "Billetera de créditos"
        verbose_name_plural = "Billeteras de créditos"

    def __str__(self):
        return f"{self.user.username}: {self.balance} créditos"


class CreditPack(models.Model):
    """Paquete que se puede comprar (catálogo mostrado en el frontend)."""

    name = models.CharField(max_length=100, verbose_name="Nombre")
    credits = models.PositiveIntegerField(verbose_name="Créditos que otorga")
    price_usd = models.DecimalField(max_digits=8, decimal_places=2, verbose_name="Precio (USD)")
    is_active = models.BooleanField(default=True, verbose_name="¿Disponible para la venta?")
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "billing_credit_pack"
        verbose_name = "Paquete de créditos"
        verbose_name_plural = "Paquetes de créditos"
        ordering = ["display_order", "price_usd"]

    def __str__(self):
        return f"{self.name} ({self.credits} créditos · ${self.price_usd})"


class PaymentTransaction(models.Model):
    """
    Registro de cada intento de pago (con PayPal o PayPhone) por un
    paquete de créditos. Se crea en PENDING al iniciar el checkout y
    pasa a APPROVED/FAILED cuando el usuario vuelve de la pasarela y
    se confirma contra la API real del proveedor (nunca se acreditan
    créditos solo porque el navegador "diga" que pagó).
    """

    PROVIDER_PAYPAL = "PAYPAL"
    PROVIDER_PAYPHONE = "PAYPHONE"
    PROVIDER_CHOICES = [
        (PROVIDER_PAYPAL, "PayPal"),
        (PROVIDER_PAYPHONE, "PayPhone"),
    ]

    STATUS_PENDING = "PENDING"
    STATUS_APPROVED = "APPROVED"
    STATUS_FAILED = "FAILED"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pendiente"),
        (STATUS_APPROVED, "Aprobado"),
        (STATUS_FAILED, "Fallido"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="payment_transactions")
    pack = models.ForeignKey(CreditPack, on_delete=models.SET_NULL, null=True, blank=True)

    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    provider_reference = models.CharField(
        max_length=150, db_index=True,
        help_text="orderId de PayPal o clientTransactionId de PayPhone",
    )

    amount_usd = models.DecimalField(max_digits=8, decimal_places=2)
    credits = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    raw_response = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "billing_payment_transaction"
        verbose_name = "Transacción de pago"
        verbose_name_plural = "Transacciones de pago"
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.status}] {self.provider} {self.provider_reference} -> {self.user.username}"


class CreditSpend(models.Model):
    """Historial de consumo de créditos (ej. al ejecutar una campaña)."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="credit_spends")
    amount = models.PositiveIntegerField()
    reason = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "billing_credit_spend"
        verbose_name = "Consumo de créditos"
        verbose_name_plural = "Consumos de créditos"
        ordering = ["-created_at"]

    def __str__(self):
        return f"-{self.amount} créditos a {self.user.username} ({self.reason})"
