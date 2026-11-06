from datetime import timedelta

import pytest

from masssend.application.ia.asistente import (
    MODELO_GUIA,
    REDACCION,
    ConsultarAsistente,
    RevisarAsistente,
    armar_mensajes,
    contexto_para,
    limpiar_respuesta,
    tema_de,
)
from masssend.application.ia.puertos import (
    EstadoGenerador,
    IGeneradorTexto,
    MensajeChat,
    TextoGenerado,
)
from masssend.domain.ia.consulta import Consulta, Turno
from masssend.domain.shared.errores import DatosInvalidos
from tests.fakes.reloj import RelojFijo


class GeneradorDePrueba:
    def __init__(self, reloj: RelojFijo) -> None:
        self._reloj = reloj
        self.prompts: list[list[MensajeChat]] = []

    def generar(self, mensajes: list[MensajeChat]) -> TextoGenerado:
        self.prompts.append(mensajes)
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


def test_los_mensajes_llevan_contexto_historial_y_pregunta_en_orden() -> None:
    consulta = Consulta.crear(
        "como compro",
        [Turno("user", "hola"), Turno("assistant", "buenas")],
    )
    assert armar_mensajes(consulta) == [
        MensajeChat("system", contexto_para("como compro")),
        MensajeChat("user", "hola"),
        MensajeChat("assistant", "buenas"),
        MensajeChat("user", "como compro"),
    ]


def test_consultar_envia_al_modelo_los_mensajes_armados() -> None:
    reloj = RelojFijo()
    generador = GeneradorDePrueba(reloj)
    ConsultarAsistente(generador, reloj).ejecutar("  como compro ", [Turno("user", "hola")])
    assert generador.prompts == [
        [
            MensajeChat("system", contexto_para("como compro")),
            MensajeChat("user", "hola"),
            MensajeChat("user", "como compro"),
        ]
    ]


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


def test_quita_el_markdown_de_la_respuesta() -> None:
    texto = "## Pasos\n1. **Entra** a Campañas.\n* Usa __{{nombre}}__ y *emojis*.\n2. Lanza 2*3"
    assert limpiar_respuesta(texto) == (
        "Pasos\n1. Entra a Campañas.\n- Usa {{nombre}} y emojis.\n2. Lanza 2*3"
    )


def test_una_respuesta_cortada_termina_en_la_ultima_linea_completa() -> None:
    texto = "1. Entra a Campañas.\n2. Pulsa Lanzar.\n3. Aseg"
    assert limpiar_respuesta(texto, completo=False) == "1. Entra a Campañas.\n2. Pulsa Lanzar."


def test_una_respuesta_cortada_en_un_parrafo_termina_en_la_ultima_oracion() -> None:
    texto = "Cada mensaje usa un crédito. Si no alcanzan, compra un paq"
    assert limpiar_respuesta(texto, completo=False) == "Cada mensaje usa un crédito."


def test_una_respuesta_completa_no_se_recorta() -> None:
    assert limpiar_respuesta("Hola, te ayudo", completo=True) == "Hola, te ayudo"


def test_consultar_entrega_la_respuesta_limpia_y_sin_el_corte() -> None:
    class GeneradorCortado(GeneradorDePrueba):
        def generar(self, mensajes: list[MensajeChat]) -> TextoGenerado:
            return TextoGenerado("1. **Crea** la campaña.\n2. Asegu", "modelo", completo=False)

    reloj = RelojFijo()
    respuesta = ConsultarAsistente(GeneradorCortado(reloj), reloj).ejecutar("como creo", [])
    assert respuesta.respuesta == "1. Crea la campaña."


@pytest.mark.parametrize(
    ("pregunta", "tema"),
    [
        ("¿Cómo creo una campaña?", "+ Nueva campaña"),
        ("¿Cómo importo mis contactos?", "Importar CSV"),
        ("¿Cómo funcionan los créditos?", "1 crédito = 1 mensaje"),
        ("Olvidé mi contraseña", "Seguridad"),
        ("¿Cómo conecto WhatsApp?", "Dispositivos vinculados"),
        ("¿Dónde veo los reportes?", "tasas de entrega"),
    ],
)
def test_cada_pregunta_de_uso_encuentra_su_seccion_de_la_guia(pregunta: str, tema: str) -> None:
    seccion = tema_de(pregunta)
    assert seccion is not None
    assert tema in seccion


def test_las_preguntas_de_uso_se_responden_con_la_guia_sin_llamar_al_modelo() -> None:
    reloj = RelojFijo()
    generador = GeneradorDePrueba(reloj)
    respuesta = ConsultarAsistente(generador, reloj).ejecutar("¿Cómo creo una campaña?", [])
    assert respuesta.modelo == MODELO_GUIA
    assert '"+ Nueva campaña"' in respuesta.respuesta
    assert generador.prompts == []


def test_pedir_un_mensaje_va_al_modelo_con_las_instrucciones_de_redaccion() -> None:
    reloj = RelojFijo()
    generador = GeneradorDePrueba(reloj)
    ConsultarAsistente(generador, reloj).ejecutar("Redacta un mensaje para mi campaña", [])
    assert generador.prompts[0][0] == MensajeChat("system", REDACCION)


def test_pedir_un_mensaje_usa_solo_las_instrucciones_de_redaccion() -> None:
    assert contexto_para("Redáctame un mensaje para promocionar un descuento del 20%") == REDACCION
    assert contexto_para("Escribe un anuncio de mi tienda") == REDACCION


def test_preguntar_como_escribir_no_es_pedir_una_redaccion() -> None:
    assert contexto_para("¿Cómo escribo el mensaje de una campaña?") != REDACCION
    assert tema_de("¿Cómo escribo el mensaje de una campaña?") is not None


def test_sin_tema_conocido_va_al_modelo_con_el_resumen_general() -> None:
    assert tema_de("hola") is None
    assert "Menú:" in contexto_para("hola")
