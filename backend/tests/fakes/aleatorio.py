class AleatorioFijo:
    """Azar predecible para comprobar resultados exactos."""

    def token(self, longitud: int) -> str:
        return "a" * longitud

    def digitos(self, cantidad: int) -> str:
        return "1" * cantidad
