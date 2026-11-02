from datetime import timedelta

import pytest

from masssend.application.ia.asistente import (
    CONTEXTO_SISTEMA,
    ConsultarAsistente,
    RevisarAsistente,
    armar_prompt,
)
from masssend.application.ia.puertos import EstadoGenerador, IGeneradorTexto, TextoGenerado
from masssend.domain.ia.consulta import Consulta, Turno
from masssend.domain.shared.errores import DatosInvalidos
from tests.fakes.reloj import RelojFijo


class GeneradorDePrueba:
    def __init__(self, reloj: RelojFijo) -> None:
        self._reloj = reloj
        self.prompts: list[str] = []

    def generar(self, prompt: str) -> TextoGenerado:
        self.prompts.append(prompt)
        self._reloj.avanzar(timedelta(milliseconds=250))
        return TextoGenerado("  hola  ", "modelo")

    def estado(self) -> EstadoGenerador:
        return EstadoGenerador(True, "modelo", True)


@pytest.mark.parametrize("pregunta", ["", "   ", "x" * 2001])
def test_rechaza_preguntas_vacias_o_largas(pregunta: str) -> None:
    with pytest.raises(DatosInvalidos) as error:
        Consulta.crear(pregunta, [])
    assert error.value.campo == "pregunta"


def test_acepta_el_largo_maximo() -> None:
    assert len(Consulta.crear("x" * 2000, []).pregunta) == 2000


def test_conserva_solo_los_ultimos_seis_turnos() -> None:
    historial = [Turno("user", str(n)) for n in range(10)]
    consulta = Consulta.crear("hola", historial)
    assert [t.contenido for t in consulta.historial] == ["4", "5", "6", "7", "8", "9"]


def test_recorta_cada_turno() -> None:
    consulta = Consulta.crear("hola", [Turno("user", "x" * 900)])
    assert len(consulta.historial[0].contenido) == 500


def test_el_prompt_lleva_contexto_historial_y_pregunta_en_orden() -> None:
    consulta = Consulta.crear(
        "como compro",
        [Turno("user", "hola"), Turno("assistant", "buenas")],
    )
    prompt = armar_prompt(consulta)
    assert prompt.startswith(CONTEXTO_SISTEMA)
    assert prompt.endswith(
        "Usuario: hola\nAsistente: buenas\nUsuario: como compro\nAsistente:"
    )


def test_consultar_limpia_el_texto_y_mide_la_latencia() -> None:
    reloj = RelojFijo()
    generador: IGeneradorTexto = GeneradorDePrueba(reloj)
    respuesta = ConsultarAsistente(generador, reloj).ejecutar("hola", [])
    assert (respuesta.respuesta, respuesta.modelo, respuesta.latencia_ms) == (
        "hola",
        "modelo",
        250,
    )


def test_una_pregunta_invalida_no_llega_al_modelo() -> None:
    reloj = RelojFijo()
    generador = GeneradorDePrueba(reloj)
    with pytest.raises(DatosInvalidos):
        ConsultarAsistente(generador, reloj).ejecutar(" ", [])
    assert generador.prompts == []


def test_revisar_informa_el_estado() -> None:
    assert RevisarAsistente(GeneradorDePrueba(RelojFijo())).ejecutar().modelo_descargado
