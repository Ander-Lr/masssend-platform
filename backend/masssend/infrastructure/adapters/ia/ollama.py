import logging

import requests

from masssend.application.ia.puertos import EstadoGenerador, MensajeChat, TextoGenerado
from masssend.domain.shared.errores import ServicioNoDisponible

logger = logging.getLogger(__name__)


class GeneradorOllama:
    def __init__(self, url: str, modelo: str, tiempo_maximo: int) -> None:
        self._url = url.rstrip("/")
        self._modelo = modelo
        self._tiempo_maximo = tiempo_maximo

    def generar(self, mensajes: list[MensajeChat]) -> TextoGenerado:
        try:
            respuesta = requests.post(
                f"{self._url}/api/chat",
                json={
                    "model": self._modelo,
                    "messages": [{"role": m.rol, "content": m.contenido} for m in mensajes],
                    "stream": False,
                    # repeat_penalty evita que un modelo pequeno entre en bucle.
                    "options": {"temperature": 0.3, "num_predict": 220, "repeat_penalty": 1.15},
                },
                timeout=self._tiempo_maximo,
            )
            respuesta.raise_for_status()
            datos = respuesta.json()
            texto = str(datos["message"]["content"])
        except (requests.RequestException, ValueError, KeyError, TypeError) as error:
            logger.warning("Ollama no respondio: %s", type(error).__name__)
            raise ServicioNoDisponible("El asistente no está disponible.") from error
        return TextoGenerado(texto, str(datos.get("model", self._modelo)))

    def estado(self) -> EstadoGenerador:
        try:
            respuesta = requests.get(f"{self._url}/api/tags", timeout=3)
            respuesta.raise_for_status()
            modelos = [m.get("name", "") for m in respuesta.json().get("models", [])]
        except (requests.RequestException, ValueError):
            return EstadoGenerador(False, self._modelo, False)
        return EstadoGenerador(True, self._modelo, self._modelo in modelos)
