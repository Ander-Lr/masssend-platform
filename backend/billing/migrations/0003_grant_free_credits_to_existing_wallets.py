# Si alguien ya había abierto la página de Créditos antes de que
# existiera el bono de bienvenida, se quedó con una billetera en 0.
# Esta migración les da el bono una sola vez (10 créditos, hardcodeado
# a propósito: si luego cambian FREE_SIGNUP_CREDITS en settings, esta
# migración histórica no debe cambiar de resultado al reejecutarse).
from django.db import migrations

FREE_SIGNUP_CREDITS = 10


def grant_bonus(apps, schema_editor):
    CreditWallet = apps.get_model("billing", "CreditWallet")
    CreditWallet.objects.filter(balance=0).update(balance=FREE_SIGNUP_CREDITS)


def revert_bonus(apps, schema_editor):
    CreditWallet = apps.get_model("billing", "CreditWallet")
    CreditWallet.objects.filter(balance=FREE_SIGNUP_CREDITS).update(balance=0)


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0002_seed_default_packs"),
    ]

    operations = [
        migrations.RunPython(grant_bonus, revert_bonus),
    ]
