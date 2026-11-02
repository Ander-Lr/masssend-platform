from masssend.application.creditos.puertos import CobroConfirmado, CobroIniciado, Paquete
from masssend.domain.shared.dinero import Dinero


class PasarelaPruebas:
    """Permite completar una compra en Postman sin salir a internet.

    datos_pasarela simula a la pasarela: resultado=rechazado y monto_cobrado.
    """

    def __init__(self, nombre: str) -> None:
        self.nombre = nombre

    def iniciar(self, paquete: Paquete, referencia: str) -> CobroIniciado:
        url = f"https://pasarela.falsa/pagar/{referencia}"
        return CobroIniciado(f"FALSA-{referencia}", url, {"falsa": True})

    def confirmar(self, referencia: str, datos: dict[str, object]) -> CobroConfirmado:
        cobrado = datos.get("monto_cobrado")
        return CobroConfirmado(
            datos.get("resultado") != "rechazado",
            Dinero.desde_decimal(str(cobrado)) if cobrado is not None else None,
            {"falsa": True},
        )
