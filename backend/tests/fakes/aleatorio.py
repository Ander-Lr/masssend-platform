class AleatorioFijo:
    """Azar predecible para comprobar resultados exactos."""

    def __init__(self) -> None:
        self._contador = 0

    def token(self, longitud: int) -> str:
        self._contador += 1
        return f"{self._contador:0{longitud}d}"

    def digitos(self, cantidad: int) -> str:
        return "1" * cantidad
