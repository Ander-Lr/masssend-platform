"""Emision y lectura de desafios, compartida por los casos de uso."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from masssend.application.shared.puertos import IAleatorio, IGeneradorIds, IReloj
from masssend.domain.identidad.desafio import Desafio, Proposito, hash_token
from masssend.domain.identidad.repositorios import IRepoDesafios
from masssend.domain.shared.errores import NoAutenticado
from masssend.domain.shared.identificadores import IdPublico

LONGITUD_TOKEN = 43


@dataclass(frozen=True, slots=True)
class DesafioEmitido:
    token: str
    expira_en: datetime


class ServicioDesafios:
    def __init__(
        self,
        repo: IRepoDesafios,
        reloj: IReloj,
        ids: IGeneradorIds,
        aleatorio: IAleatorio,
    ) -> None:
        self._repo = repo
        self._reloj = reloj
        self._ids = ids
        self._aleatorio = aleatorio

    def emitir(
        self, proposito: Proposito, vigencia: timedelta, cuenta_id: IdPublico | None = None
    ) -> DesafioEmitido:
        token = self._aleatorio.token(LONGITUD_TOKEN)
        expira_en = self._reloj.ahora() + vigencia
        self._repo.agregar(
            Desafio(self._ids.nuevo(), proposito, hash_token(token), expira_en, cuenta_id)
        )
        return DesafioEmitido(token, expira_en)

    def exigir(self, token: str, proposito: Proposito) -> Desafio:
        """Devuelve el desafio vigente, retenido hasta confirmar."""
        desafio = self._repo.bloquear_por_hash(hash_token(token), proposito)
        if desafio is None:
            raise NoAutenticado("El desafío no es válido o venció.")
        desafio.exigir_vigente(self._reloj.ahora())
        return desafio

    def consumir(self, desafio: Desafio) -> None:
        desafio.consumir(self._reloj.ahora())
        self._repo.guardar(desafio)
