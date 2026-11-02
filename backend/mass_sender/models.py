from django.conf import settings
from django.db import models
import os

class ApiProvider(models.Model):
    phone_number_id = models.CharField(max_length=100, unique=True, verbose_name="ID del Número de Teléfono")
    waba_id = models.CharField(max_length=100, blank=True, null=True, verbose_name="WABA ID")
    display_number = models.CharField(max_length=50, blank=True, null=True, verbose_name="Número a mostrar")
    business_name = models.CharField(max_length=150, blank=True, null=True, verbose_name="Nombre del Negocio")
    access_token = models.TextField(blank=True, null=True, verbose_name="Token de Acceso")
    is_active = models.BooleanField(default=True, verbose_name="¿Está activo?")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'api_providers'
        verbose_name = "Proveedor de API"
        verbose_name_plural = "Proveedores de API"

    def __str__(self):
        return f"{self.business_name or 'Sin Nombre'} ({self.display_number or self.phone_number_id})"


class Contact(models.Model):
    # owner nulo = contacto sin asignar (mensaje entrante de un número
    # desconocido); solo el staff lo ve.
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='contacts',
        verbose_name="Dueño",
    )
    phone_number = models.CharField(max_length=50, verbose_name="Número de WhatsApp")
    full_name = models.CharField(max_length=150, blank=True, null=True, verbose_name="Nombre Completo")
    tags = models.CharField(max_length=255, blank=True, null=True, help_text="Para segmentar (ej: clientes, leads)", verbose_name="Etiquetas")
    custom_data = models.JSONField(blank=True, null=True, help_text="Variables extra para plantillas", verbose_name="Datos Extra")
    is_opted_out = models.BooleanField(default=False, verbose_name="¿No desea recibir mensajes?")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'contacts'
        verbose_name = "Contacto"
        verbose_name_plural = "Contactos"
        constraints = [
            # Dos usuarios pueden tener el mismo número en su libreta.
            models.UniqueConstraint(fields=['owner', 'phone_number'], name='uniq_contact_owner_phone'),
            # NULL no choca en un UNIQUE compuesto: los sin dueño necesitan el suyo.
            models.UniqueConstraint(
                fields=['phone_number'],
                condition=models.Q(owner__isnull=True),
                name='uniq_contact_unassigned_phone',
            ),
        ]

    def __str__(self):
        return f"{self.full_name or 'Sin nombre'} - {self.phone_number}"


def campaign_media_upload_path(instance, filename):
    """Guarda el archivo en media/campaigns/<id>/<filename>"""
    ext = os.path.splitext(filename)[1].lower()
    return f'campaigns/{filename}'


class Campaign(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Borrador'),
        ('scheduled', 'Programada'),
        ('running', 'En Curso'),
        ('completed', 'Completada'),
        ('cancelled', 'Cancelada'),
    ]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='campaigns',
        verbose_name="Dueño",
        help_text="Usuario propietario de la campaña. Requerido para aislar el acceso entre cuentas.",
    )
    name = models.CharField(max_length=150, verbose_name="Nombre de la Campaña")
    message_template = models.TextField(verbose_name="Plantilla del Mensaje", help_text="Usa {{variable}} para personalizar.")
    media_url = models.URLField(max_length=500, blank=True, null=True, verbose_name="URL de Imagen/Adjunto (opcional)")
    media_file = models.FileField(
        upload_to=campaign_media_upload_path,
        blank=True,
        null=True,
        verbose_name="Subir Imagen o Video",
        help_text="Sube una imagen (JPG, PNG, WEBP) o video (MP4). Si subes archivo, tiene prioridad sobre la URL."
    )
    target_tags = models.CharField(
        max_length=255, blank=True, null=True,
        verbose_name="Filtrar por etiqueta",
        help_text="Deja en blanco para enviar a TODOS. Escribe una etiqueta (ej: cliente) para enviar solo a contactos con esa etiqueta."
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name="Estado")
    scheduled_at = models.DateTimeField(blank=True, null=True, verbose_name="Programada para")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'campaigns'
        verbose_name = "Campaña"
        verbose_name_plural = "Campañas"

    def get_media_url(self):
        """Devuelve la URL del media: primero el archivo subido, luego la URL manual."""
        if self.media_file:
            return self.media_file.url
        return self.media_url or ''

    def __str__(self):
        return self.name


class CampaignProgress(models.Model):
    """Rastreo en tiempo real del progreso de envío masivo."""
    campaign = models.OneToOneField(Campaign, on_delete=models.CASCADE, related_name='progress', verbose_name="Campaña")
    total = models.IntegerField(default=0, verbose_name="Total de contactos")
    sent = models.IntegerField(default=0, verbose_name="Enviados")
    failed = models.IntegerField(default=0, verbose_name="Fallidos")
    is_running = models.BooleanField(default=False, verbose_name="¿En ejecución?")
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(blank=True, null=True)
    last_error = models.TextField(blank=True, null=True, verbose_name="Último error")

    class Meta:
        db_table = 'campaign_progress'
        verbose_name = "Progreso de Campaña"
        verbose_name_plural = "Progreso de Campañas"

    def __str__(self):
        return f"Progreso: {self.campaign.name} ({self.sent}/{self.total})"


class Message(models.Model):
    DIRECTION_CHOICES = [
        ('inbound', 'Entrante'),
        ('outbound', 'Saliente'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('sent', 'Enviado'),
        ('delivered', 'Entregado'),
        ('read', 'Leído'),
        ('failed', 'Fallido'),
    ]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='whatsapp_messages',
        verbose_name="Dueño",
    )
    provider = models.ForeignKey(ApiProvider, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Proveedor")
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, null=True, blank=True, verbose_name="Campaña")
    phone_number = models.CharField(max_length=50, verbose_name="Teléfono Destino/Origen")
    direction = models.CharField(max_length=15, choices=DIRECTION_CHOICES, verbose_name="Dirección")
    message_type = models.CharField(max_length=50, default='text', verbose_name="Tipo de Mensaje")
    content = models.TextField(verbose_name="Contenido")
    delivery_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Estado de Entrega")
    wpp_message_id  = models.CharField(max_length=200, blank=True, null=True, verbose_name="ID de WhatsApp", db_index=True)
    error_log       = models.TextField(blank=True, null=True, verbose_name="Log de Error")
    sent_at         = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'messages'
        verbose_name = "Mensaje"
        verbose_name_plural = "Mensajes"

    def __str__(self):
        return f"{self.get_direction_display()} - {self.phone_number} - {self.get_delivery_status_display()}"
