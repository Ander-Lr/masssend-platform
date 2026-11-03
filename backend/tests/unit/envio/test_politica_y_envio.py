import pytest

from masssend.domain.envio.envio import Envio, EstadoEnvio, Progreso
from masssend.domain.envio.lanzamiento import Lanzamiento
from masssend.domain.envio.politica import PoliticaEnvio
from masssend.domain.shared.errores import DatosInvalidos, EstadoInvalido
from tests.fakes.ids import GeneradorIdsSecuencial

IDS = GeneradorIdsSecuencial()


@pytest.mark.parametrize(
    ("orden", "segundos"),
    [(0, 0), (1, 3), (49, 147), (50, 270), (51, 273), (100, 540)],
)
def test_conserva_el_ritmo_del_sistema_actual(orden: int, segundos: int) -> None:
    """3 s entre mensajes y 120 s de pausa cada 50, como en mass_sender/admin.py."""
    assert PoliticaEnvio().retraso(orden) == segundos


def test_duracion_de_una_campana() -> None:
    politica = PoliticaEnvio()
    assert politica.duracion(0) == 0
    assert politica.duracion(1) == 0
    assert politica.duracion(51) == 270


def test_una_politica_sin_esperas_para_pruebas() -> None:
    assert PoliticaEnvio(0, 50, 0).retraso(500) == 0


@pytest.mark.parametrize(("entre", "lote", "pausa"), [(-1, 50, 120), (3, 0, 120), (3, 50, -1)])
def test_la_politica_valida_sus_valores(entre: int, lote: int, pausa: int) -> None:
    with pytest.raises(DatosInvalidos):
        PoliticaEnvio(entre, lote, pausa)


def test_el_orden_no_es_negativo() -> None:
    with pytest.raises(DatosInvalidos):
        PoliticaEnvio().retraso(-1)


def envio() -> Envio:
    return Envio(IDS.nuevo(), IDS.nuevo(), IDS.nuevo(), IDS.nuevo(), "593991112222", 0)


def test_un_envio_nace_pendiente_y_se_cierra_una_vez() -> None:
    e = envio()
    assert e.pendiente
    e.marcar_enviado("wamid.1")
    assert (e.estado, e.id_externo) == (EstadoEnvio.ENVIADO, "wamid.1")
    with pytest.raises(EstadoInvalido):
        e.marcar_enviado("wamid.2")
    with pytest.raises(EstadoInvalido):
        e.cancelar()


@pytest.mark.parametrize(
    ("accion", "estado"),
    [
        ("marcar_fallido", EstadoEnvio.FALLIDO),
        ("omitir", EstadoEnvio.OMITIDO),
    ],
)
def test_fallar_y_omitir_guardan_el_motivo(accion: str, estado: EstadoEnvio) -> None:
    e = envio()
    getattr(e, accion)("x" * 600)
    assert e.estado is estado
    assert e.detalle == "x" * 500


def test_cancelar_un_pendiente() -> None:
    e = envio()
    e.cancelar()
    assert (e.estado, e.detalle) == (EstadoEnvio.CANCELADO, None)


def test_progreso() -> None:
    progreso = Progreso(total=10, enviados=5, fallidos=1, omitidos=1, cancelados=0)
    assert (progreso.procesados, progreso.pendientes, progreso.porcentaje) == (7, 3, 70)
    assert not progreso.terminado
    assert Progreso(total=2, enviados=1, cancelados=1).terminado


def test_sin_envios_no_hay_avance_ni_termino() -> None:
    assert (Progreso().porcentaje, Progreso().terminado) == (0, False)


def test_un_lanzamiento_necesita_destinatarios() -> None:
    with pytest.raises(DatosInvalidos):
        Lanzamiento(IDS.nuevo(), IDS.nuevo(), IDS.nuevo(), 0)
