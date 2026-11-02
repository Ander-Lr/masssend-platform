from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mass_sender', '0002_campaign_media_file_alter_campaign_media_url_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='message',
            name='wpp_message_id',
            field=models.CharField(
                blank=True,
                db_index=True,
                max_length=200,
                null=True,
                verbose_name='ID de WhatsApp'
            ),
        ),
    ]
