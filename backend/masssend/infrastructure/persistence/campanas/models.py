"""Vista de la v1 sobre la tabla contacts del sistema actual.

managed en False: Django no crea ni altera la tabla, solo la lee y escribe.
public_id lo agrega la migracion mass_sender 0007_public_ids.
"""

from django.conf import settings
from django.db import models


class ContactoFila(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.DO_NOTHING,
        db_column="owner_id",
        db_constraint=False,
        null=True,
        related_name="+",
    )
    public_id = models.UUIDField(unique=True)
    phone_number = models.CharField(max_length=50)
    full_name = models.CharField(max_length=150, null=True, blank=True)
    tags = models.CharField(max_length=255, null=True, blank=True)
    custom_data = models.JSONField(null=True, blank=True)
    is_opted_out = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "contacts"
