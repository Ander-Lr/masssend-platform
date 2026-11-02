from datetime import UTC, datetime, timedelta

import pytest

from masssend.application.shared.puertos import (
    IAleatorio,
    IGeneradorIds,
    IReloj,
    IUnidadDeTrabajo,
)
from tests.fakes.aleatorio import AleatorioFijo
from tests.fakes.ids import GeneradorIdsSecuencial
from tests.fakes.reloj import RelojFijo
from tests.fakes.unidad_de_trabajo import UnidadDeTrabajoFalsa


def test_el_reloj_falso_cumple_el_puerto_y_avanza() -> None:
    reloj: IReloj = RelojFijo()
    assert reloj.ahora() == datetime(2026, 1, 1, tzinfo=UTC)
    falso = RelojFijo()
    falso.avanzar(timedelta(seconds=3))
    assert falso.ahora().second == 3


def test_el_reloj_exige_zona_horaria() -> None:
    with pytest.raises(ValueError):
        RelojFijo(datetime(2026, 1, 1))


def test_generador_y_azar_cumplen_sus_puertos() -> None:
    generador: IGeneradorIds = GeneradorIdsSecuencial()
    aleatorio: IAleatorio = AleatorioFijo()
    assert generador.nuevo().version == 7
    assert len(aleatorio.token(8)) == 8
    assert aleatorio.digitos(6) == "111111"


def test_confirmar_ejecuta_los_efectos_externos() -> None:
    uow: IUnidadDeTrabajo = UnidadDeTrabajoFalsa()
    enviados: list[str] = []
    with uow as transaccion:
        transaccion.al_confirmar(lambda: enviados.append("correo"))
        assert enviados == []
    assert enviados == ["correo"]


def test_una_excepcion_revierte_y_cancela_los_efectos() -> None:
    uow = UnidadDeTrabajoFalsa()
    enviados: list[str] = []
    with pytest.raises(RuntimeError), uow as transaccion:
        transaccion.al_confirmar(lambda: enviados.append("correo"))
        raise RuntimeError("fallo")
    assert enviados == []
    assert (uow.confirmaciones, uow.reversiones) == (0, 1)
