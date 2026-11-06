"""Contenedor del modulo de IA."""

from django.conf import settings

from masssend.application.ia.asistente import ConsultarAsistente, RevisarAsistente
from masssend.application.ia.puertos import IGeneradorTexto
from masssend.infrastructure.adapters.ia.falso import GeneradorFalso
from masssend.infrastructure.adapters.ia.ollama import GeneradorOllama
from masssend.infrastructure.composition.creditos import contenedor_creditos
from masssend.infrastructure.composition.root import contenedor as raiz


class ContenedorIa:
    def _generador(self) -> IGeneradorTexto:
        if settings.GENERADOR_TEXTO == "fake":
            return GeneradorFalso()
        return GeneradorOllama(
            settings.OLLAMA_URL, settings.OLLAMA_MODEL, settings.OLLAMA_TIMEOUT_SECONDS
        )

    def consultar(self) -> ConsultarAsistente:
        return ConsultarAsistente(
            self._generador(), raiz.reloj(), contenedor_creditos.saldo_para_asistente()
        )

    def revisar(self) -> RevisarAsistente:
        return RevisarAsistente(self._generador())


contenedor_ia = ContenedorIa()
