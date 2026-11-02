"""Comprueba que la integración corre sobre PostgreSQL con las migraciones."""

import pytest
from django.db import connection


@pytest.mark.django_db
def test_usa_postgresql() -> None:
    assert connection.vendor == "postgresql"


@pytest.mark.django_db
def test_tablas_compartidas_existen() -> None:
    tablas = connection.introspection.table_names()
    assert {"contacts", "campaigns", "messages"} <= set(tablas)
