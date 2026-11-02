from masssend.application.creditos.puertos import IPasarelaPago
from masssend.domain.shared.errores import DatosInvalidos
from masssend.infrastructure.adapters.pagos.falsa import PasarelaPruebas
from masssend.infrastructure.adapters.pagos.heredadas import paypal, payphone

CREADORAS = {"PAYPAL": paypal, "PAYPHONE": payphone}


class SelectorPasarelas:
    def __init__(self, usar_falsa: bool) -> None:
        self._usar_falsa = usar_falsa

    def pasarela(self, nombre: str) -> IPasarelaPago:
        clave = nombre.strip().upper()
        if clave not in CREADORAS:
            raise DatosInvalidos("La pasarela de pago no está soportada.", "pasarela")
        return PasarelaPruebas(clave) if self._usar_falsa else CREADORAS[clave]()
