from uuid import UUID

import pytest

from masssend.domain.shared.errores import DatosInvalidos
from masssend.domain.shared.identificadores import id_publico
from tests.fakes.ids import GeneradorIdsSecuencial

UUID7 = "0190a6e0-0000-7000-8000-000000000001"
UUID4 = "9f1c0a52-3c3e-4b0e-8a57-2f1f4a3d1b11"


def test_acepta_uuid7_como_texto_o_uuid() -> None:
    assert id_publico(UUID7) == UUID(UUID7)
    assert id_publico(UUID(UUID7)) == UUID(UUID7)


@pytest.mark.parametrize("valor", [UUID4, "no-es-un-uuid", ""])
def test_rechaza_lo_que_no_es_uuid7(valor: str) -> None:
    with pytest.raises(DatosInvalidos) as error:
        id_publico(valor, "campana_id")
    assert error.value.campo == "campana_id"


def test_el_generador_falso_entrega_uuid7_distintos() -> None:
    generador = GeneradorIdsSecuencial()
    primero, segundo = generador.nuevo(), generador.nuevo()
    assert primero != segundo
    assert id_publico(primero) == primero
