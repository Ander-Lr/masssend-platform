"""Tablas propias del envio de la v1.

Cada envio es tambien la cola: programado_para dice cuando le toca salir y
el trabajador toma los pendientes vencidos. Si el proceso se reinicia, nada
se pierde, porque el estado vive en la base y no en la memoria de un hilo.
"""

from django.db import models

from mass_sender.models import Message


class EnvioFila(models.Model):
    id = models.UUIDField(primary_key=True)
    campana_id = models.UUIDField(db_index=True)
    owner_id = models.UUIDField()
    contacto_id = models.UUIDField()
    telefono = models.CharField(max_length=50)
    orden = models.PositiveIntegerField()
    estado = models.CharField(max_length=12, default="pendiente")
    id_externo = models.CharField(max_length=200, null=True, blank=True)
    detalle = models.CharField(max_length=500, null=True, blank=True)
    texto = models.TextField(null=True, blank=True)
    # Null hasta que la cola lo publica, ya confirmado el lanzamiento.
    programado_para = models.DateTimeField(null=True, blank=True)
    # El mensaje del sistema actual, para que historial y reportes lo vean.
    mensaje = models.ForeignKey(
        Message, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "envio_envio"
        indexes = [
            models.Index(
                fields=["programado_para"],
                condition=models.Q(estado="pendiente"),
                name="envio_pendiente_vencido",
            ),
            models.Index(fields=["campana_id", "estado"], name="envio_campana_estado"),
        ]


class LanzamientoFila(models.Model):
    campana_id = models.UUIDField(primary_key=True)
    owner_id = models.UUIDField()
    reserva_id = models.UUIDField()
    total = models.PositiveIntegerField()
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "envio_lanzamiento"
