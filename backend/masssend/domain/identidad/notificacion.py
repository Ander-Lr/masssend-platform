"""Notificacion por correo y validacion de sus adjuntos."""

from dataclasses import dataclass

from masssend.domain.identidad.correo import validar_correo
from masssend.domain.shared.errores import DatosInvalidos

MAX_ASUNTO = 120
MAX_TITULO = 100
MAX_MENSAJE = 3000
FIRMA_POR_DEFECTO = "MassSend"

CABECERA_PDF = b"%PDF-"
CABECERA_PNG = b"\x89PNG\r\n\x1a\n"
CABECERA_JPG = b"\xff\xd8\xff"
CABECERA_ZIP = b"PK\x03\x04"

TIPOS_PERMITIDOS = {
    "application/pdf": CABECERA_PDF,
    "image/png": CABECERA_PNG,
    "image/jpeg": CABECERA_JPG,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": CABECERA_ZIP,
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": CABECERA_ZIP,
}


@dataclass(frozen=True, slots=True)
class Adjunto:
    nombre: str
    tipo: str
    contenido: bytes

    @classmethod
    def crear(cls, nombre: str, tipo: str, contenido: bytes, maximo_mb: int) -> "Adjunto":
        cabecera = TIPOS_PERMITIDOS.get(tipo)
        if cabecera is None:
            raise DatosInvalidos("Usa un archivo PDF, DOCX, XLSX, PNG o JPG.", "archivo")
        if len(contenido) > maximo_mb * 1024 * 1024:
            raise DatosInvalidos(f"El archivo supera los {maximo_mb} MB.", "archivo")
        if not contenido.startswith(cabecera):
            raise DatosInvalidos("El contenido no coincide con el tipo de archivo.", "archivo")
        return cls(nombre, tipo, contenido)


@dataclass(frozen=True, slots=True)
class Notificacion:
    destinatario: str
    asunto: str
    titulo: str
    mensaje: str
    firma: str
    adjunto: Adjunto | None = None

    @classmethod
    def crear(
        cls,
        destinatario: str,
        asunto: str,
        titulo: str,
        mensaje: str,
        firma: str = "",
        adjunto: Adjunto | None = None,
    ) -> "Notificacion":
        correo = validar_correo(destinatario)
        asunto_limpio = _texto(asunto, "asunto", MAX_ASUNTO)
        if "\n" in asunto_limpio or "\r" in asunto_limpio:
            raise DatosInvalidos("El asunto no admite saltos de línea.", "asunto")
        return cls(
            correo,
            asunto_limpio,
            _texto(titulo, "titulo", MAX_TITULO),
            _texto(mensaje, "mensaje", MAX_MENSAJE),
            firma.strip() or FIRMA_POR_DEFECTO,
            adjunto,
        )


def _texto(valor: str, campo: str, maximo: int) -> str:
    limpio = valor.strip()
    if not limpio:
        raise DatosInvalidos("Este campo es obligatorio.", campo)
    if len(limpio) > maximo:
        raise DatosInvalidos(f"Admite {maximo} caracteres como máximo.", campo)
    return limpio
