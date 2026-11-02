"""Desafio: prueba temporal de un solo uso. Solo se guarda el hash del token."""

import hashlib
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from masssend.domain.shared.errores import NoAutenticado
from masssend.domain.shared.identificadores import IdPublico


class Proposito(StrEnum):
    TOTP = "totp"
    ENROLAMIENTO = "enrolamiento"
    RECUPERACION = "recuperacion"
    GOOGLE = "google"


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@dataclass
class Desafio:
    id: IdPublico
    proposito: Proposito
    hash_token: str
    expira_en: datetime
    cuenta_id: IdPublico | None = None
    usado_en: datetime | None = None

    def exigir_vigente(self, ahora: datetime) -> None:
        if self.usado_en is not None or self.expira_en <= ahora:
            raise NoAutenticado("El desafío no es válido o venció.")

    def consumir(self, ahora: datetime) -> None:
        self.exigir_vigente(ahora)
        self.usado_en = ahora
