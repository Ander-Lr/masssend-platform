import pytest

from masssend.application.identidad.notificaciones import (
    ConsultarCola,
    ControlarCola,
    EnviarNotificacion,
)
from masssend.application.identidad.puertos import IColaNotificaciones, TareaCorreo
from masssend.domain.identidad.notificacion import (
    CABECERA_JPG,
    CABECERA_PDF,
    CABECERA_PNG,
    CABECERA_ZIP,
    FIRMA_POR_DEFECTO,
    Adjunto,
    Notificacion,
)
from masssend.domain.shared.errores import DatosInvalidos
from masssend.domain.shared.identificadores import IdPublico
from masssend.domain.shared.paginacion import Pagina, PeticionPagina
from tests.fakes.ids import GeneradorIdsSecuencial

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class ColaDePrueba:
    def __init__(self) -> None:
        self.encoladas: list[tuple[Notificacion, IdPublico]] = []
        self.pausa = False

    def encolar(self, notificacion: Notificacion, tarea_id: IdPublico) -> None:
        self.encoladas.append((notificacion, tarea_id))

    def tareas(self, peticion: PeticionPagina) -> Pagina[TareaCorreo]:
        return Pagina(())

    def pausada(self) -> bool:
        return self.pausa

    def pausar(self) -> None:
        self.pausa = True

    def reanudar(self) -> None:
        self.pausa = False


def notificacion(**cambios: str) -> Notificacion:
    datos = {
        "destinatario": " ANA@Prueba.local ",
        "asunto": "Asunto",
        "titulo": "Titulo",
        "mensaje": "Mensaje",
        **cambios,
    }
    return Notificacion.crear(
        datos["destinatario"], datos["asunto"], datos["titulo"], datos["mensaje"]
    )


def test_normaliza_y_pone_la_firma_por_defecto() -> None:
    creada = notificacion()
    assert (creada.destinatario, creada.firma) == ("ana@prueba.local", FIRMA_POR_DEFECTO)


@pytest.mark.parametrize(
    ("cambio", "campo"),
    [
        ({"destinatario": "mal"}, "correo"),
        ({"asunto": " "}, "asunto"),
        ({"asunto": "x" * 121}, "asunto"),
        ({"asunto": "Hola\nBcc: otro@prueba.local"}, "asunto"),
        ({"asunto": "Hola\rBcc: otro@prueba.local"}, "asunto"),
        ({"titulo": ""}, "titulo"),
        ({"titulo": "x" * 101}, "titulo"),
        ({"mensaje": ""}, "mensaje"),
        ({"mensaje": "x" * 3001}, "mensaje"),
    ],
)
def test_valida_cada_campo(cambio: dict[str, str], campo: str) -> None:
    with pytest.raises(DatosInvalidos) as error:
        notificacion(**cambio)
    assert error.value.campo == campo


@pytest.mark.parametrize(
    ("tipo", "cabecera"),
    [
        ("application/pdf", CABECERA_PDF),
        ("image/png", CABECERA_PNG),
        ("image/jpeg", CABECERA_JPG),
        (DOCX, CABECERA_ZIP),
    ],
)
def test_acepta_tipos_permitidos_con_su_contenido(tipo: str, cabecera: bytes) -> None:
    assert Adjunto.crear("a", tipo, cabecera + b"resto", 1).tipo == tipo


def test_rechaza_un_tipo_no_permitido() -> None:
    with pytest.raises(DatosInvalidos):
        Adjunto.crear("a.exe", "application/x-msdownload", b"MZ", 1)


def test_rechaza_un_ejecutable_declarado_como_pdf() -> None:
    with pytest.raises(DatosInvalidos):
        Adjunto.crear("a.pdf", "application/pdf", b"MZ\x90\x00", 1)


def test_rechaza_un_archivo_demasiado_grande() -> None:
    with pytest.raises(DatosInvalidos):
        Adjunto.crear("a.pdf", "application/pdf", CABECERA_PDF + b"0" * 1024 * 1024, 1)


def test_enviar_encola_con_id_uuid7() -> None:
    cola = ColaDePrueba()
    puerto: IColaNotificaciones = cola
    tarea = EnviarNotificacion(puerto, GeneradorIdsSecuencial()).ejecutar(notificacion())
    assert tarea.version == 7
    assert cola.encoladas[0][1] == tarea


def test_controlar_pausa_y_reanuda() -> None:
    cola = ColaDePrueba()
    control = ControlarCola(cola)
    control.pausar()
    assert ConsultarCola(cola).ejecutar(PeticionPagina())[1]
    control.reanudar()
    assert not ConsultarCola(cola).ejecutar(PeticionPagina())[1]
