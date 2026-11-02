"""Comprueba que los anillos y módulos de la arquitectura existen."""

import importlib

import pytest

MODULOS = ["shared", "identidad", "creditos", "ia", "campanas", "envio"]
PAQUETES = [
    "masssend.infrastructure.adapters",
    "masssend.infrastructure.persistence",
    "masssend.infrastructure.composition",
    "masssend.interfaces.http.shared",
    "masssend.interfaces.workers",
    *[f"masssend.domain.{modulo}" for modulo in MODULOS],
    *[f"masssend.application.{modulo}" for modulo in MODULOS],
]


@pytest.mark.parametrize("paquete", PAQUETES)
def test_paquete_existe(paquete: str) -> None:
    assert importlib.import_module(paquete)
