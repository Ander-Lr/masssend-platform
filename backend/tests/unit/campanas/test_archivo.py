import pytest

from masssend.domain.campanas.archivo import MB, ArchivoCampana, tipo_por_contenido
from masssend.domain.shared.errores import DatosInvalidos

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32
JPG = b"\xff\xd8\xff\xe0" + b"0" * 32
WEBP = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"0" * 32
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"0" * 32


@pytest.mark.parametrize(
    ("nombre", "contenido", "tipo"),
    [
        ("foto.png", PNG, "image/png"),
        ("FOTO.JPG", JPG, "image/jpeg"),
        ("foto.jpeg", JPG, "image/jpeg"),
        ("foto.webp", WEBP, "image/webp"),
        ("video.mp4", MP4, "video/mp4"),
    ],
)
def test_acepta_imagenes_y_videos(nombre: str, contenido: bytes, tipo: str) -> None:
    archivo = ArchivoCampana.crear(nombre, contenido)
    assert archivo.tipo == tipo
    assert archivo.es_video is (tipo == "video/mp4")


def test_un_png_renombrado_como_mp4_se_rechaza() -> None:
    with pytest.raises(DatosInvalidos) as error:
        ArchivoCampana.crear("video.mp4", PNG)
    assert error.value.campo == "archivo"
    assert "no coincide" in error.value.mensaje


@pytest.mark.parametrize(
    ("nombre", "contenido"),
    [
        ("documento.pdf", b"%PDF-1.7"),
        ("programa.exe", b"MZ"),
        ("sin_extension", PNG),
        ("foto.png", b""),
        ("foto.png", b"texto plano que dice ser png"),
        ("foto.jpg", PNG),
    ],
)
def test_rechaza_otros_formatos_o_contenidos(nombre: str, contenido: bytes) -> None:
    with pytest.raises(DatosInvalidos) as error:
        ArchivoCampana.crear(nombre, contenido)
    assert error.value.campo == "archivo"


@pytest.mark.parametrize(
    ("nombre", "cabecera", "limite"), [("foto.png", PNG, 5), ("video.mp4", MP4, 16)]
)
def test_respeta_los_limites_de_whatsapp(nombre: str, cabecera: bytes, limite: int) -> None:
    justo = cabecera + b"0" * (limite * MB - len(cabecera))
    assert ArchivoCampana.crear(nombre, justo)
    with pytest.raises(DatosInvalidos) as error:
        ArchivoCampana.crear(nombre, justo + b"0")
    assert f"{limite} MB" in error.value.mensaje


def test_quita_la_ruta_del_nombre() -> None:
    assert ArchivoCampana.crear("C:\\fotos\\../promo.png", PNG).nombre == "promo.png"


def test_contenido_desconocido() -> None:
    assert tipo_por_contenido(b"hola") is None
