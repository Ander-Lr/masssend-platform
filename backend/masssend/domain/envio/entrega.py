"""Lo que WhatsApp informa despues de enviar: entrega, lectura y baja.

El estado de entrega solo avanza. Los avisos de WhatsApp pueden llegar
desordenados o repetidos: un "entregado" tardio no deshace un "leido".
"""

import re
import unicodedata
from enum import StrEnum


class EstadoEntrega(StrEnum):
    PENDIENTE = "pendiente"
    ENVIADO = "enviado"
    ENTREGADO = "entregado"
    LEIDO = "leido"
    FALLIDO = "fallido"


_ORDEN = {
    EstadoEntrega.PENDIENTE: 0,
    EstadoEntrega.FALLIDO: 0,
    EstadoEntrega.ENVIADO: 1,
    EstadoEntrega.ENTREGADO: 2,
    EstadoEntrega.LEIDO: 3,
}


def avanza(actual: EstadoEntrega, nuevo: EstadoEntrega) -> bool:
    """True si nuevo es posterior a actual. Un fallido solo reemplaza a un pendiente."""
    if nuevo is EstadoEntrega.FALLIDO:
        return actual is EstadoEntrega.PENDIENTE
    return _ORDEN[nuevo] > _ORDEN[actual]


PALABRAS_BAJA = frozenset({"BAJA", "DARME DE BAJA", "STOP"})
_NO_LETRAS = re.compile(r"[^A-Z ]+")


def es_solicitud_de_baja(texto: str) -> bool:
    """El mensaje completo debe ser la palabra BAJA, sin importar tildes, signos
    ni mayusculas. Una frase que solo la contiene no cuenta: "no me den de baja"."""
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    limpio = " ".join(_NO_LETRAS.sub(" ", sin_tildes.upper()).split())
    return limpio in PALABRAS_BAJA
