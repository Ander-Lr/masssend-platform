from masssend.application.ia.puertos import EstadoGenerador, MensajeChat, TextoGenerado

MODELO = "generador-falso"


class GeneradorFalso:
    """Respuesta fija para probar la API sin un modelo cargado."""

    def generar(self, mensajes: list[MensajeChat]) -> TextoGenerado:
        return TextoGenerado("Respuesta de prueba del asistente.", MODELO)

    def estado(self) -> EstadoGenerador:
        return EstadoGenerador(True, MODELO, True)
