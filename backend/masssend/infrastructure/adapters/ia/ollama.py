import logging

import requests

from masssend.application.ia.puertos import EstadoGenerador, TextoGenerado
from masssend.domain.shared.errores import ServicioNoDisponible

logger = logging.getLogger(__name__)


class GeneradorOllama:
    def __init__(self, url: str, modelo: str, tiempo_maximo: int) -> None:
        self._url = url.rstrip("/")
        self._modelo = modelo
        self._tiempo_maximo = tiempo_maximo

    def generar(self, prompt: str) -> TextoGenerado:
        try:
            respuesta = requests.post(
                f"{self._url}/api/generate",
                json={
                    "model": self._modelo,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.3, "num_predict": 220},
                },
                timeout=self._tiempo_maximo,
            )
            respuesta.raise_for_status()
            datos = respuesta.json()
        except (requests.RequestException, ValueError) as error:
            logger.warning("Ollama no respondio: %s", type(error).__name__)
            raise ServicioNoDisponible("El asistente no está disponible.") from error
        return TextoGenerado(str(datos.get("response", "")), str(datos.get("model", self._modelo)))

    def estado(self) -> EstadoGenerador:
        try:
            respuesta = requests.get(f"{self._url}/api/tags", timeout=3)
            respuesta.raise_for_status()
            modelos = [m.get("name", "") for m in respuesta.json().get("models", [])]
        except (requests.RequestException, ValueError):
            return EstadoGenerador(False, self._modelo, False)
        return EstadoGenerador(True, self._modelo, self._modelo in modelos)
