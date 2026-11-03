import pytest

from masssend.domain.campanas.contacto import Contacto, limpiar_etiquetas
from masssend.domain.campanas.telefono import Telefono
from masssend.domain.shared.errores import DatosInvalidos
from tests.fakes.ids import GeneradorIdsSecuencial

IDS = GeneradorIdsSecuencial()
ANA = IDS.nuevo()
LUIS = IDS.nuevo()
TELEFONO = Telefono.desde_texto("0991112222")


def contacto(**datos: object) -> Contacto:
    nuevo = Contacto.nuevo(IDS.nuevo(), ANA, TELEFONO, "Pedro", "vip")
    for campo, valor in datos.items():
        setattr(nuevo, campo, valor)
    return nuevo


def test_sin_nombre_se_muestra_con_su_numero() -> None:
    assert Contacto.nuevo(IDS.nuevo(), ANA, TELEFONO, "   ").nombre == "593991112222"


def test_el_nombre_se_limpia_y_tiene_limite() -> None:
    assert Contacto.nuevo(IDS.nuevo(), ANA, TELEFONO, "  Pedro  ").nombre == "Pedro"
    with pytest.raises(DatosInvalidos) as error:
        Contacto.nuevo(IDS.nuevo(), ANA, TELEFONO, "x" * 151)
    assert error.value.campo == "nombre"


def test_las_etiquetas_se_limpian_sin_repetidas() -> None:
    assert limpiar_etiquetas(" vip, cliente,,vip , ") == ("vip", "cliente")
    assert limpiar_etiquetas(["lead", " lead", ""]) == ("lead",)
    assert limpiar_etiquetas("") == ()


def test_las_etiquetas_tienen_limite() -> None:
    with pytest.raises(DatosInvalidos) as error:
        limpiar_etiquetas("x" * 256)
    assert error.value.campo == "etiquetas"


def test_pertenece_solo_a_su_dueno() -> None:
    c = contacto()
    assert c.pertenece_a(ANA)
    assert not c.pertenece_a(LUIS)


def test_renombrar_y_etiquetar() -> None:
    c = contacto()
    c.renombrar("")
    c.etiquetar("lead, vip")
    assert c.nombre == "593991112222"
    assert c.etiquetas == ("lead", "vip")


def test_completar_datos_no_borra_los_demas() -> None:
    c = contacto(datos={"ciudad": "Quito"})
    c.completar_datos({"notas": "llamar"})
    assert c.datos == {"ciudad": "Quito", "notas": "llamar"}


@pytest.mark.parametrize(
    ("buscadas", "coincide"),
    [([], True), (["vip"], True), (["lead", "vip"], True), (["lead"], False)],
)
def test_coincide_con_alguna_etiqueta(buscadas: list[str], coincide: bool) -> None:
    assert contacto().tiene_alguna_etiqueta(buscadas) is coincide


def test_la_baja_es_repetible_y_reversible() -> None:
    c = contacto()
    assert c.puede_recibir
    c.dar_de_baja()
    c.dar_de_baja()
    assert not c.puede_recibir
    c.reactivar()
    assert c.puede_recibir
