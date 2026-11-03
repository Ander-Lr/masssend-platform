import pytest

from masssend.domain.campanas.campana import (
    MAX_MENSAJE,
    Campana,
    EstadoCampana,
    personalizar,
)
from masssend.domain.shared.errores import DatosInvalidos, EstadoInvalido
from tests.fakes.ids import GeneradorIdsSecuencial

IDS = GeneradorIdsSecuencial()
ANA = IDS.nuevo()
LUIS = IDS.nuevo()


def borrador(**datos: object) -> Campana:
    campana = Campana.nueva(IDS.nuevo(), ANA, " Promo ", " Hola {{nombre}} ", "vip, lead")
    for campo, valor in datos.items():
        setattr(campana, campo, valor)
    return campana


def test_nace_como_borrador_y_limpia_sus_datos() -> None:
    campana = borrador()
    assert campana.estado is EstadoCampana.BORRADOR
    assert (campana.nombre, campana.mensaje, campana.etiquetas) == (
        "Promo",
        "Hola {{nombre}}",
        ("vip", "lead"),
    )
    assert campana.adjunto is None
    assert campana.pertenece_a(ANA) and not campana.pertenece_a(LUIS)


@pytest.mark.parametrize(
    ("nombre", "mensaje", "campo"),
    [
        ("", "Hola", "nombre"),
        ("x" * 151, "Hola", "nombre"),
        ("Promo", "   ", "mensaje"),
        ("Promo", "x" * (MAX_MENSAJE + 1), "mensaje"),
    ],
)
def test_valida_nombre_y_mensaje(nombre: str, mensaje: str, campo: str) -> None:
    with pytest.raises(DatosInvalidos) as error:
        Campana.nueva(IDS.nuevo(), ANA, nombre, mensaje)
    assert error.value.campo == campo


def test_editar_cambia_solo_lo_indicado() -> None:
    campana = borrador()
    campana.editar(mensaje="Nuevo", etiquetas=[])
    assert (campana.nombre, campana.mensaje, campana.etiquetas) == ("Promo", "Nuevo", ())


def test_editar_con_un_dato_invalido_no_cambia_nada() -> None:
    campana = borrador()
    with pytest.raises(DatosInvalidos):
        campana.editar(nombre="Otra", mensaje="")
    assert campana.nombre == "Promo"


@pytest.mark.parametrize(
    "estado", [EstadoCampana.EN_CURSO, EstadoCampana.COMPLETADA, EstadoCampana.CANCELADA]
)
def test_solo_un_borrador_se_modifica(estado: EstadoCampana) -> None:
    campana = borrador(estado=estado)
    with pytest.raises(EstadoInvalido):
        campana.editar(nombre="Otra")
    with pytest.raises(EstadoInvalido):
        campana.adjuntar("ref")
    with pytest.raises(EstadoInvalido):
        campana.quitar_adjunto()


def test_adjuntar_y_quitar() -> None:
    campana = borrador()
    campana.adjuntar("ref")
    assert campana.adjunto == "ref"
    campana.quitar_adjunto()
    assert campana.adjunto is None


def test_recorrido_completo() -> None:
    campana = borrador()
    recorrido = [campana.estado]
    campana.iniciar()
    recorrido.append(campana.estado)
    campana.completar()
    recorrido.append(campana.estado)
    assert recorrido == [
        EstadoCampana.BORRADOR,
        EstadoCampana.EN_CURSO,
        EstadoCampana.COMPLETADA,
    ]


@pytest.mark.parametrize("estado", [EstadoCampana.BORRADOR, EstadoCampana.EN_CURSO])
def test_se_cancela_un_borrador_o_una_en_curso(estado: EstadoCampana) -> None:
    campana = borrador(estado=estado)
    campana.cancelar()
    assert campana.estado is EstadoCampana.CANCELADA


@pytest.mark.parametrize(
    ("estado", "accion"),
    [
        (EstadoCampana.BORRADOR, "completar"),
        (EstadoCampana.EN_CURSO, "iniciar"),
        (EstadoCampana.COMPLETADA, "iniciar"),
        (EstadoCampana.COMPLETADA, "cancelar"),
        (EstadoCampana.CANCELADA, "iniciar"),
        (EstadoCampana.CANCELADA, "cancelar"),
    ],
)
def test_transiciones_prohibidas(estado: EstadoCampana, accion: str) -> None:
    campana = borrador(estado=estado)
    with pytest.raises(EstadoInvalido):
        getattr(campana, accion)()
    assert campana.estado is estado


def test_una_campana_en_curso_no_se_elimina() -> None:
    with pytest.raises(EstadoInvalido):
        borrador(estado=EstadoCampana.EN_CURSO).exigir_eliminable()
    for estado in (EstadoCampana.BORRADOR, EstadoCampana.COMPLETADA, EstadoCampana.CANCELADA):
        borrador(estado=estado).exigir_eliminable()


@pytest.mark.parametrize(
    ("plantilla", "nombre", "datos", "esperado"),
    [
        ("Hola {{nombre}}", "Pedro", None, "Hola Pedro"),
        ("Hola {{ nombre }}!", "Pedro", None, "Hola Pedro!"),
        ("Hola {{nombre}}", "  ", None, "Hola Amigo"),
        ("{{nombre}} de {{ciudad}}", "Ana", {"ciudad": "Quito"}, "Ana de Quito"),
        ("Codigo {{codigo}}", "Ana", {}, "Codigo {{codigo}}"),
        ("Sin variables", "Ana", None, "Sin variables"),
    ],
)
def test_personalizar(
    plantilla: str, nombre: str, datos: dict[str, str] | None, esperado: str
) -> None:
    assert personalizar(plantilla, nombre, datos) == esperado


def test_un_dato_llamado_nombre_no_pisa_el_nombre() -> None:
    assert borrador().mensaje_para("Pedro", {"nombre": "Otro"}) == "Hola Pedro"
