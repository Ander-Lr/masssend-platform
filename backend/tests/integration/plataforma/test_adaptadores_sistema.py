"""Los adaptadores reales cumplen los mismos puertos que los fakes."""

import re

import pytest
from django.contrib.auth import get_user_model

from masssend.application.shared.puertos import (
    IAleatorio,
    IGeneradorIds,
    IReloj,
    IUnidadDeTrabajo,
)
from masssend.domain.shared.identificadores import id_publico
from masssend.infrastructure.composition.root import contenedor


def test_el_reloj_real_lleva_zona_horaria() -> None:
    reloj: IReloj = contenedor.reloj()
    assert reloj.ahora().tzinfo is not None


def test_el_generador_real_entrega_uuid7_rfc_unicos_y_ordenables() -> None:
    generador: IGeneradorIds = contenedor.generador_ids()
    ids = [generador.nuevo() for _ in range(1000)]
    assert len(set(ids)) == 1000
    assert all(id_publico(valor).variant == "specified in RFC 4122" for valor in ids)
    tiempos = [valor.int >> 80 for valor in ids]
    assert tiempos == sorted(tiempos)


def test_el_azar_real_respeta_formato_y_longitud() -> None:
    aleatorio: IAleatorio = contenedor.aleatorio()
    assert re.fullmatch(r"[A-Za-z0-9_-]{32}", aleatorio.token(32))
    assert re.fullmatch(r"\d{6}", aleatorio.digitos(6))
    assert aleatorio.token(32) != aleatorio.token(32)


@pytest.mark.django_db(transaction=True)
def test_confirmar_guarda_y_ejecuta_el_efecto() -> None:
    uow: IUnidadDeTrabajo = contenedor.unidad_de_trabajo()
    efectos: list[str] = []
    with uow as transaccion:
        get_user_model().objects.create_user("ana")
        transaccion.al_confirmar(lambda: efectos.append("correo"))
        assert efectos == []
    assert efectos == ["correo"]
    assert get_user_model().objects.filter(username="ana").exists()


@pytest.mark.django_db(transaction=True)
def test_una_excepcion_revierte_y_cancela_el_efecto() -> None:
    uow = contenedor.unidad_de_trabajo()
    efectos: list[str] = []
    with pytest.raises(RuntimeError), uow as transaccion:
        get_user_model().objects.create_user("luis")
        transaccion.al_confirmar(lambda: efectos.append("correo"))
        raise RuntimeError("fallo")
    assert efectos == []
    assert not get_user_model().objects.filter(username="luis").exists()
