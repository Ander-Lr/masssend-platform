from masssend.application.creditos.puertos import IPasarelaPago
from masssend.domain.shared.errores import DatosInvalidos
from masssend.infrastructure.adapters.pagos.falsa import PasarelaPruebas
from masssend.infrastructure.adapters.pagos.heredadas import paypal
from masssend.infrastructure.adapters.pagos.payphone import payphone

CREADORAS = {"PAYPAL": paypal, "PAYPHONE": payphone}


class SelectorPasarelas:
    """Las pasarelas que no estan en reales se simulan."""

    def __init__(self, reales: frozenset[str]) -> None:
        self._reales = reales

    def pasarela(self, nombre: str) -> IPasarelaPago:
        clave = nombre.strip().upper()
        if clave not in CREADORAS:
            raise DatosInvalidos("La pasarela de pago no está soportada.", "pasarela")
        return CREADORAS[clave]() if clave in self._reales else PasarelaPruebas(clave)
