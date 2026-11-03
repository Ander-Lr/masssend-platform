"""
Identificadores publicos UUIDv7 para la API v1.

Es una de las excepciones aprobadas a la regla que congela el legacy: solo
agrega una columna public_id a contacts, campaigns y messages, sin tocar las
claves actuales. Los modelos de mass_sender no cambian, por eso la migracion
no altera el estado de Django; la columna la leen los modelos de masssend.

La base genera el valor. Asi tambien lo reciben las filas que crean las
rutas anteriores, que no conocen la columna.
"""

from django.db import migrations

TABLAS = ("contacts", "campaigns", "messages")

FUNCION_POSTGRES = """
CREATE OR REPLACE FUNCTION masssend_uuid_v7() RETURNS uuid AS $$
    SELECT encode(
        set_bit(set_bit(
            overlay(uuid_send(gen_random_uuid())
                placing substring(int8send(floor(extract(epoch FROM clock_timestamp()) * 1000)::bigint) FROM 3)
                FROM 1 FOR 6),
        52, 1), 53, 1),
    'hex')::uuid;
$$ LANGUAGE sql VOLATILE;
"""

# Django guarda los UUID de SQLite como 32 caracteres hexadecimales.
UUID7_SQLITE = (
    "printf('%012x', CAST((julianday('now') - 2440587.5) * 86400000 AS INTEGER))"
    " || '7' || substr(lower(hex(randomblob(2))), 2, 3)"
    " || substr('89ab', 1 + (abs(random()) % 4), 1)"
    " || substr(lower(hex(randomblob(2))), 2, 3)"
    " || lower(hex(randomblob(6)))"
)


def _postgres(cursor, crear):
    if crear:
        cursor.execute(FUNCION_POSTGRES)
    for tabla in TABLAS:
        if crear:
            # El valor por defecto volatil llena tambien las filas existentes.
            cursor.execute(
                f"ALTER TABLE {tabla} ADD COLUMN public_id uuid NOT NULL "
                f"DEFAULT masssend_uuid_v7() UNIQUE"
            )
        else:
            cursor.execute(f"ALTER TABLE {tabla} DROP COLUMN public_id")
    if not crear:
        cursor.execute("DROP FUNCTION masssend_uuid_v7()")


def _sqlite(cursor, crear):
    for tabla in TABLAS:
        if crear:
            cursor.execute(f"ALTER TABLE {tabla} ADD COLUMN public_id char(32) NULL")
            cursor.execute(f"UPDATE {tabla} SET public_id = {UUID7_SQLITE}")
            cursor.execute(f"CREATE UNIQUE INDEX {tabla}_public_id_uniq ON {tabla} (public_id)")
            cursor.execute(
                f"CREATE TRIGGER {tabla}_public_id AFTER INSERT ON {tabla} "
                f"WHEN NEW.public_id IS NULL BEGIN "
                f"UPDATE {tabla} SET public_id = {UUID7_SQLITE} WHERE rowid = NEW.rowid; END"
            )
        else:
            cursor.execute(f"DROP TRIGGER {tabla}_public_id")
            cursor.execute(f"DROP INDEX {tabla}_public_id_uniq")
            cursor.execute(f"ALTER TABLE {tabla} DROP COLUMN public_id")


def _aplicar(schema_editor, crear):
    vendor = schema_editor.connection.vendor
    with schema_editor.connection.cursor() as cursor:
        if vendor == "postgresql":
            _postgres(cursor, crear)
        elif vendor == "sqlite":
            _sqlite(cursor, crear)
        else:
            raise NotImplementedError(f"Base de datos no soportada: {vendor}")


def agregar(apps, schema_editor):
    _aplicar(schema_editor, crear=True)


def quitar(apps, schema_editor):
    _aplicar(schema_editor, crear=False)


class Migration(migrations.Migration):
    dependencies = [
        ("mass_sender", "0006_contact_message_owner"),
    ]

    operations = [
        migrations.RunPython(agregar, quitar),
    ]
