"""Firma de los avisos del gateway: HMAC-SHA256 con marca de tiempo.

Antes el gateway mandaba siempre el mismo token en Authorization: quien lo
viera una vez podia repetir cualquier aviso para siempre. Ahora cada aviso
lleva su firma, calculada sobre la marca de tiempo y el cuerpo exacto:

    X-MassSend-Tiempo: 1762190000
    X-MassSend-Firma:  sha256=<hex de HMAC(secreto, "1762190000." + cuerpo)>

Un cuerpo alterado, un secreto distinto o un aviso de mas de 5 minutos no pasan.
Solo usa la biblioteca estandar, igual que el gateway usa crypto de Node.
"""

import hashlib
import hmac

CABECERA_TIEMPO = "X-MassSend-Tiempo"
CABECERA_FIRMA = "X-MassSend-Firma"
TOLERANCIA_SEGUNDOS = 300
PREFIJO = "sha256="


class FirmaInvalida(Exception):
    pass


def firmar(cuerpo: bytes, tiempo: str, secreto: str) -> str:
    resumen = hmac.new(secreto.encode(), tiempo.encode() + b"." + cuerpo, hashlib.sha256)
    return PREFIJO + resumen.hexdigest()


def verificar(
    cuerpo: bytes, tiempo: str | None, firma: str | None, secreto: str, ahora: float
) -> None:
    """Lanza FirmaInvalida con el motivo. Sin secreto configurado, rechaza todo."""
    if not secreto:
        raise FirmaInvalida("El servidor no tiene configurado el secreto del gateway.")
    if not tiempo or not firma:
        raise FirmaInvalida("Falta la firma del gateway.")
    try:
        momento = int(tiempo)
    except ValueError as error:
        raise FirmaInvalida("La marca de tiempo no es válida.") from error
    if abs(ahora - momento) > TOLERANCIA_SEGUNDOS:
        raise FirmaInvalida("El aviso venció; puede ser una repetición.")
    if not hmac.compare_digest(firmar(cuerpo, tiempo, secreto), firma):
        raise FirmaInvalida("La firma no es válida.")
