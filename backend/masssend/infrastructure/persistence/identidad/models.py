"""Tablas propias de la v1. Complementan auth_user y email_auth sin modificarlas."""

from django.conf import settings
from django.db import models


class CuentaIdentidad(models.Model):
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cuenta_identidad"
    )
    public_id = models.UUIDField(unique=True)
    ultimo_paso_totp = models.BigIntegerField(null=True, blank=True)
    fallos_totp = models.PositiveSmallIntegerField(default=0)
    bloqueada_hasta = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "identidad_cuenta"


class DesafioIdentidad(models.Model):
    id = models.UUIDField(primary_key=True)
    cuenta = models.ForeignKey(
        CuentaIdentidad, on_delete=models.CASCADE, null=True, blank=True, related_name="desafios"
    )
    proposito = models.CharField(max_length=20)
    hash_token = models.CharField(max_length=64, unique=True)
    expira_en = models.DateTimeField()
    usado_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "identidad_desafio"
