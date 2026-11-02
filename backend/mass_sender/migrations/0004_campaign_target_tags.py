from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mass_sender', '0003_message_wpp_message_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='campaign',
            name='target_tags',
            field=models.CharField(
                blank=True,
                max_length=255,
                null=True,
                verbose_name='Filtrar por etiqueta',
                help_text='Deja en blanco para enviar a TODOS. Escribe una etiqueta (ej: cliente) para enviar solo a contactos con esa etiqueta.'
            ),
        ),
    ]
