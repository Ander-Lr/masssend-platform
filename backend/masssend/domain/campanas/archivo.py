"""Imagen o video adjunto de una campana.

El tipo se comprueba por el contenido, no por el nombre: un PNG renombrado
como .mp4 se rechaza. Los limites son los de WhatsApp.
"""

from dataclasses import dataclass

from masssend.domain.shared.errores import DatosInvalidos

MB = 1024 * 1024
TIPOS_POR_EXTENSION = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".mp4": "video/mp4",
}
LIMITE_MB = {"image/jpeg": 5, "image/png": 5, "image/webp": 5, "video/mp4": 16}
FORMATOS = "JPG, PNG, WEBP o MP4"


def tipo_por_contenido(contenido: bytes) -> str | None:
    """Reconoce el formato por sus primeros bytes."""
    if contenido.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if contenido.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if contenido[:4] == b"RIFF" and contenido[8:12] == b"WEBP":
        return "image/webp"
    if contenido[4:8] == b"ftyp":
        return "video/mp4"
    return None


def _extension(nombre: str) -> str:
    punto = nombre.rfind(".")
    return nombre[punto:].lower() if punto != -1 else ""


@dataclass(frozen=True, slots=True)
class ArchivoCampana:
    nombre: str
    tipo: str
    contenido: bytes

    @classmethod
    def crear(cls, nombre: str, contenido: bytes) -> "ArchivoCampana":
        nombre_limpio = nombre.replace("\\", "/").rsplit("/", 1)[-1].strip()
        declarado = TIPOS_POR_EXTENSION.get(_extension(nombre_limpio))
        if declarado is None:
            raise DatosInvalidos(f"Usa una imagen o video {FORMATOS}.", "archivo")
        if not contenido:
            raise DatosInvalidos("El archivo está vacío.", "archivo")
        limite = LIMITE_MB[declarado]
        if len(contenido) > limite * MB:
            raise DatosInvalidos(f"El archivo supera el límite de {limite} MB.", "archivo")
        real = tipo_por_contenido(contenido)
        if real != declarado:
            raise DatosInvalidos(
                "El contenido del archivo no coincide con su extensión.", "archivo"
            )
        return cls(nombre_limpio, real, contenido)

    @property
    def es_video(self) -> bool:
        return self.tipo.startswith("video/")
