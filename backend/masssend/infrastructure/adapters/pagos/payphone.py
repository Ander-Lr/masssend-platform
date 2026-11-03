"""Boton de pago de PayPhone: Prepare, redireccion y Confirm (API V2).

Reemplaza en la v1 al adaptador heredado, que usaba API Links: ese flujo no
redirige al comercio ni permite confirmar el cobro.
https://docs.payphone.app/boton-de-pago
"""

import logging
from typing import Any

import requests
from django.conf import settings

from masssend.application.creditos.puertos import CobroConfirmado, CobroIniciado, Paquete
from masssend.domain.shared.dinero import Dinero
from masssend.domain.shared.errores import DatosInvalidos, ServicioNoDisponible

logger = logging.getLogger(__name__)

RUTA_PREPARAR = "/api/button/Prepare"
RUTA_CONFIRMAR = "/api/button/V2/Confirm"
APROBADA = 3
NO_DISPONIBLE = "PayPhone no está disponible."
# Solo se guarda lo necesario para auditar; la respuesta trae correo y tarjeta.
CAMPOS_GUARDADOS = (
    "statusCode",
    "transactionStatus",
    "transactionId",
    "clientTransactionId",
    "amount",
    "currency",
    "authorizationCode",
    "date",
    "message",
    "paymentId",
    "payWithCard",
    "payWithPayPhone",
)


def id_cliente(referencia: str) -> str:
    """PayPhone admite 15 caracteres; la cola de un UUIDv7 es aleatoria."""
    return "MS" + referencia.replace("-", "")[-13:].upper()


def id_transaccion(valor: object) -> int:
    # str() evita que True cuente como 1.
    try:
        numero = int(str(valor))
    except ValueError:
        numero = 0
    if numero <= 0:
        raise DatosInvalidos(
            "Falta el id que PayPhone agrega a la URL de retorno.", "datos_pasarela"
        )
    return numero


def monto(respuesta: dict[str, Any]) -> Dinero | None:
    try:
        return Dinero(int(respuesta["amount"]), str(respuesta.get("currency") or "USD"))
    except (KeyError, TypeError, ValueError, DatosInvalidos):
        return None


def resumen(datos: dict[str, Any]) -> dict[str, object]:
    return {campo: datos[campo] for campo in CAMPOS_GUARDADOS if campo in datos}


class PasarelaPayphone:
    nombre = "PAYPHONE"

    def __init__(self, token: str, tienda: str, base_url: str, retorno: str) -> None:
        self._token = token
        self._tienda = tienda
        self._base_url = base_url.rstrip("/")
        self._retorno = retorno

    def iniciar(self, paquete: Paquete, referencia: str) -> CobroIniciado:
        centavos = paquete.precio.centavos
        cliente = id_cliente(referencia)
        datos = self._enviar(
            RUTA_PREPARAR,
            {
                "amount": centavos,
                "amountWithoutTax": centavos,
                "currency": paquete.precio.moneda,
                "clientTransactionId": cliente,
                "storeId": self._tienda,
                "reference": f"MassSend - {paquete.nombre}"[:100],
                "responseUrl": self._retorno,
                "cancellationUrl": self._retorno,
            },
        )
        url = datos.get("payWithCard") or datos.get("payWithPayPhone")
        if not isinstance(url, str) or not url.startswith("https://"):
            logger.warning("PayPhone no devolvio la URL de pago")
            raise ServicioNoDisponible(NO_DISPONIBLE)
        return CobroIniciado(cliente, url, resumen(datos))

    def confirmar(self, referencia: str, datos: dict[str, object]) -> CobroConfirmado:
        transaccion = id_transaccion(datos.get("id"))
        respuesta = self._enviar(RUTA_CONFIRMAR, {"id": transaccion, "clientTxId": referencia})
        # El id llega por el navegador: se exige que sea de esta misma compra.
        aprobado = (
            respuesta.get("statusCode") == APROBADA
            and respuesta.get("clientTransactionId") == referencia
        )
        return CobroConfirmado(aprobado, monto(respuesta), resumen(respuesta))

    def _enviar(self, ruta: str, cuerpo: dict[str, object]) -> dict[str, Any]:
        try:
            respuesta = requests.post(
                f"{self._base_url}{ruta}",
                json=cuerpo,
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "Content-Type": "application/json",
                },
                timeout=15,
            )
        except requests.RequestException as error:
            logger.warning("PayPhone no respondio: %s", type(error).__name__)
            raise ServicioNoDisponible(NO_DISPONIBLE) from error
        try:
            datos = respuesta.json()
        except ValueError:
            datos = None
        if not isinstance(datos, dict):
            logger.warning("PayPhone respondio %s sin JSON", respuesta.status_code)
            raise ServicioNoDisponible(NO_DISPONIBLE)
        if respuesta.status_code in (400, 404, 422):
            mensaje = str(datos.get("message") or "solicitud rechazada")[:200]
            raise DatosInvalidos(f"PayPhone rechazó la solicitud: {mensaje}", "datos_pasarela")
        if respuesta.status_code >= 300:
            # 401 y 403 suelen ser un token vencido o de otra aplicacion.
            logger.warning("PayPhone respondio %s", respuesta.status_code)
            raise ServicioNoDisponible(NO_DISPONIBLE)
        return datos


def payphone() -> PasarelaPayphone:
    if not (settings.PAYPHONE_TOKEN and settings.PAYPHONE_STORE_ID):
        raise ServicioNoDisponible("PayPhone no está configurado.")
    return PasarelaPayphone(
        settings.PAYPHONE_TOKEN,
        settings.PAYPHONE_STORE_ID,
        settings.PAYPHONE_BASE_URL,
        settings.PAYPHONE_RETORNO_V1,
    )
