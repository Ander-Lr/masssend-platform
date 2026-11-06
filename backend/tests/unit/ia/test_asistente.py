from datetime import timedelta

import pytest

from masssend.application.ia.asistente import (
    FUERA_DE_TEMA,
    MODELO_CUENTA,
    MODELO_GUIA,
    REDACCION,
    SALUDO,
    ConsultarAsistente,
    RevisarAsistente,
    armar_mensajes,
    limpiar_respuesta,
    normalizar,
    pide_redaccion,
    pide_saldo,
    tema_de,
)
from masssend.application.ia.puertos import (
    EstadoGenerador,
    IGeneradorTexto,
    ISaldoCreditos,
    MensajeChat,
    SaldoCuenta,
    TextoGenerado,
)
from masssend.domain.ia.consulta import Consulta, Turno
from masssend.domain.shared.errores import DatosInvalidos
from masssend.domain.shared.identificadores import IdPublico, id_publico
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


class SaldoDePrueba:
    def __init__(self, disponible: int = 210, reservado: int = 0) -> None:
        self.valor = SaldoCuenta(disponible, reservado)
        self.consultas: list[IdPublico] = []

    def saldo(self, owner_id: IdPublico) -> SaldoCuenta:
        self.consultas.append(owner_id)
        return self.valor


DUENO = id_publico("01a1b1a2-263c-7e70-bd55-951526f0fd1f")


def asistente(saldo: SaldoDePrueba | None = None) -> tuple[ConsultarAsistente, GeneradorDePrueba]:
    reloj = RelojFijo()
    generador = GeneradorDePrueba(reloj)
    # Los dobles cumplen los puertos: mypy lo comprueba en estas asignaciones.
    puerto_generador: IGeneradorTexto = generador
    puerto_saldo: ISaldoCreditos = saldo or SaldoDePrueba()
    return ConsultarAsistente(puerto_generador, reloj, puerto_saldo), generador


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


def test_los_mensajes_llevan_redaccion_historial_y_pregunta_en_orden() -> None:
    consulta = Consulta.crear("redacta otro", [Turno("user", "hola"), Turno("assistant", "buenas")])
    assert armar_mensajes(consulta) == [
        MensajeChat("system", REDACCION),
        MensajeChat("user", "hola"),
        MensajeChat("assistant", "buenas"),
        MensajeChat("user", "redacta otro"),
    ]


def test_pedir_un_mensaje_va_al_modelo_limpio_y_con_latencia() -> None:
    servicio, generador = asistente()
    respuesta = servicio.ejecutar(DUENO, "  Redacta un mensaje para mi tienda ", [])
    assert generador.prompts[0][0] == MensajeChat("system", REDACCION)
    assert generador.prompts[0][-1] == MensajeChat("user", "Redacta un mensaje para mi tienda")
    assert (respuesta.respuesta, respuesta.modelo, respuesta.latencia_ms) == ("hola", "modelo", 250)


def test_una_redaccion_cortada_termina_en_la_ultima_idea_completa() -> None:
    class GeneradorCortado(GeneradorDePrueba):
        def generar(self, mensajes: list[MensajeChat]) -> TextoGenerado:
            texto = "Hola {{nombre}}, **20%** de descuento.\nVen hoy y apro"
            return TextoGenerado(texto, "m", False)

    reloj = RelojFijo()
    servicio = ConsultarAsistente(GeneradorCortado(reloj), reloj, SaldoDePrueba())
    respuesta = servicio.ejecutar(DUENO, "Escribe un mensaje de descuento", [])
    assert respuesta.respuesta == "Hola {{nombre}}, 20% de descuento."


@pytest.mark.parametrize(
    "pregunta", ["cuantos creditos tengo", "¿Cuál es mi saldo?", "créditos disponibles"]
)
def test_preguntar_por_el_saldo_responde_con_el_de_la_cuenta(pregunta: str) -> None:
    saldo = SaldoDePrueba(disponible=210, reservado=5)
    servicio, generador = asistente(saldo)
    respuesta = servicio.ejecutar(DUENO, pregunta, [])
    assert respuesta.modelo == MODELO_CUENTA
    assert respuesta.respuesta.startswith("Tienes 210 créditos disponibles.")
    assert "5 reservados" in respuesta.respuesta
    assert saldo.consultas == [DUENO]
    assert generador.prompts == []


def test_sin_saldo_sugiere_comprar() -> None:
    servicio, _ = asistente(SaldoDePrueba(disponible=0))
    assert "comprar" in servicio.ejecutar(DUENO, "cuantos creditos me quedan", []).respuesta


def test_preguntar_el_precio_no_es_preguntar_el_saldo() -> None:
    assert not pide_saldo("¿Cuántos créditos cuesta un mensaje?")
    assert tema_de("¿Cuántos créditos cuesta un mensaje?") is not None


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
def test_las_preguntas_de_uso_se_responden_con_la_guia(pregunta: str, tema: str) -> None:
    servicio, generador = asistente()
    respuesta = servicio.ejecutar(DUENO, pregunta, [])
    assert respuesta.modelo == MODELO_GUIA
    assert tema in respuesta.respuesta
    assert generador.prompts == []


@pytest.mark.parametrize("pregunta", ["hola", "¡Buenas tardes!", "Hola, qué tal"])
def test_un_saludo_presenta_lo_que_puede_hacer(pregunta: str) -> None:
    servicio, generador = asistente()
    assert servicio.ejecutar(DUENO, pregunta, []).respuesta == SALUDO
    assert generador.prompts == []


@pytest.mark.parametrize(
    "pregunta",
    ["¿Cuál es la capital de Roma?", "cuéntame un chiste", "¿Quién ganó el mundial?", "2+2"],
)
def test_una_pregunta_ajena_no_llega_al_modelo(pregunta: str) -> None:
    servicio, generador = asistente()
    assert servicio.ejecutar(DUENO, pregunta, []).respuesta == FUERA_DE_TEMA
    assert generador.prompts == []


def test_preguntar_como_escribir_no_es_pedir_una_redaccion() -> None:
    assert not pide_redaccion("¿Cómo escribo el mensaje de una campaña?")
    assert pide_redaccion("Redáctame un mensaje para promocionar un descuento del 20%")
    assert pide_redaccion("Escribe un anuncio de mi tienda")


def test_una_pregunta_invalida_no_llega_al_modelo() -> None:
    servicio, generador = asistente()
    with pytest.raises(DatosInvalidos):
        servicio.ejecutar(DUENO, " ", [])
    assert generador.prompts == []


def test_revisar_informa_el_estado() -> None:
    reloj = RelojFijo()
    assert RevisarAsistente(GeneradorDePrueba(reloj)).ejecutar().disponible


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


def test_quita_los_hashtags_del_final_del_mensaje() -> None:
    texto = "¡Hola {{nombre}}, te dejo un descuento del 20%! #descuentos #bienvenido #primavera"
    assert limpiar_respuesta(texto) == "¡Hola {{nombre}}, te dejo un descuento del 20%!"
    assert limpiar_respuesta("Usa el código #VERANO hoy.") == "Usa el código #VERANO hoy."


def test_normaliza_mayusculas_tildes_y_signos() -> None:
    assert normalizar("¿Cómo cambio mi CONTRASEÑA?") == "como cambio mi contrasena"


@pytest.mark.parametrize(
    ("pregunta", "tema"),
    [
        ("como me conecto con wasap", "Dispositivos vinculados"),
        ("como vinculo el wpp", "Dispositivos vinculados"),
        ("conectar el guasap", "Dispositivos vinculados"),
        ("como creo una camapaña", "+ Nueva campaña"),
        ("quiero hacer una campania", "+ Nueva campaña"),
        ("como agrego contatos", "Importar CSV"),
        ("inportar contactos de excel", "Importar CSV"),
        ("cuanto cuestan los paquetes", "1 crédito = 1 mensaje"),
        ("olvide mi contrasena", "Seguridad"),
    ],
)
def test_tolera_faltas_de_escritura_y_formas_comunes(pregunta: str, tema: str) -> None:
    seccion = tema_de(pregunta)
    assert seccion is not None
    assert tema in seccion


@pytest.mark.parametrize(
    "pregunta",
    [
        "cuentame un chiste",
        "cual es la capital de roma",
        "en que segundo empieza",
        "me gusta la comida",
    ],
)
def test_el_parecido_no_confunde_palabras_distintas(pregunta: str) -> None:
    assert tema_de(pregunta) is None


def test_el_saldo_tolera_faltas() -> None:
    assert pide_saldo("cuantos credtos tengo")


@pytest.mark.parametrize("pregunta", ["holaa", "holi", "graciass", "muchas gracias"])
def test_los_saludos_toleran_variaciones(pregunta: str) -> None:
    servicio, generador = asistente()
    respuesta = servicio.ejecutar(DUENO, pregunta, []).respuesta
    assert respuesta != FUERA_DE_TEMA
    assert generador.prompts == []
