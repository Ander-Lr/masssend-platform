import secrets


class AleatorioSeguro:
    def token(self, longitud: int) -> str:
        return secrets.token_urlsafe(longitud)[:longitud]

    def digitos(self, cantidad: int) -> str:
        return "".join(secrets.choice("0123456789") for _ in range(cantidad))
