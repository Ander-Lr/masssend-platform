# Siembra automática de paquetes de créditos por defecto: así ningún
# usuario depende de que un admin entre al panel de Django a crear el
# catálogo a mano. Se puede editar/agregar más después desde /admin/
# si se quiere, pero no es obligatorio para poder comprar créditos.
from django.db import migrations


DEFAULT_PACKS = [
    {"name": "Básico", "credits": 50, "price_usd": "2.00", "display_order": 1},
    {"name": "Estándar", "credits": 150, "price_usd": "5.00", "display_order": 2},
    {"name": "Pro", "credits": 500, "price_usd": "15.00", "display_order": 3},
]


def seed_packs(apps, schema_editor):
    CreditPack = apps.get_model("billing", "CreditPack")
    for data in DEFAULT_PACKS:
        CreditPack.objects.get_or_create(name=data["name"], defaults=data)


def remove_seeded_packs(apps, schema_editor):
    CreditPack = apps.get_model("billing", "CreditPack")
    CreditPack.objects.filter(name__in=[p["name"] for p in DEFAULT_PACKS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_packs, remove_seeded_packs),
    ]
