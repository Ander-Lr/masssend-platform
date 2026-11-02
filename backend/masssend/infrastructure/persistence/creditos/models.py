"""Reservas de la v1. El saldo sigue en billing_credit_wallet, sin modificarla."""

from django.conf import settings
from django.db import models


class ReservaCreditos(models.Model):
    id = models.UUIDField(primary_key=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reservas_creditos"
    )
    campana_id = models.UUIDField(db_index=True)
    cantidad = models.PositiveIntegerField()
    restante = models.PositiveIntegerField()
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "creditos_reserva"
        indexes = [
            models.Index(
                fields=["usuario"],
                condition=models.Q(restante__gt=0),
                name="creditos_reserva_abierta",
            )
        ]


class ConsumoCredito(models.Model):
    reserva = models.ForeignKey(
        ReservaCreditos, on_delete=models.CASCADE, related_name="consumos"
    )
    mensaje_id = models.UUIDField()
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "creditos_consumo"
        constraints = [
            models.UniqueConstraint(
                fields=["reserva", "mensaje_id"], name="creditos_consumo_unico"
            )
        ]
