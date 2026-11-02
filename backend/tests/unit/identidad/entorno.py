"""Arma los casos de uso con fakes."""

from dataclasses import dataclass, field
from datetime import timedelta

from masssend.application.identidad.desafios import ServicioDesafios
from masssend.domain.identidad.cuenta import Cuenta
from tests.fakes.aleatorio import AleatorioFijo
from tests.fakes.identidad import (
    ColaCorreosFalsa,
    EmisorTokensFalso,
    HasherFalso,
    RepoCuentasMemoria,
    RepoDesafiosMemoria,
    TotpFalso,
)
from tests.fakes.ids import GeneradorIdsSecuencial
from tests.fakes.reloj import RelojFijo
from tests.fakes.unidad_de_trabajo import UnidadDeTrabajoFalsa

VIGENCIA = timedelta(minutes=5)


@dataclass
class Entorno:
    cuentas: RepoCuentasMemoria = field(default_factory=RepoCuentasMemoria)
    repo_desafios: RepoDesafiosMemoria = field(default_factory=RepoDesafiosMemoria)
    hasher: HasherFalso = field(default_factory=HasherFalso)
    totp: TotpFalso = field(default_factory=TotpFalso)
    cola: ColaCorreosFalsa = field(default_factory=ColaCorreosFalsa)
    tokens: EmisorTokensFalso = field(default_factory=EmisorTokensFalso)
    uow: UnidadDeTrabajoFalsa = field(default_factory=UnidadDeTrabajoFalsa)
    reloj: RelojFijo = field(default_factory=RelojFijo)
    ids: GeneradorIdsSecuencial = field(default_factory=GeneradorIdsSecuencial)
    aleatorio: AleatorioFijo = field(default_factory=AleatorioFijo)

    @property
    def desafios(self) -> ServicioDesafios:
        return ServicioDesafios(self.repo_desafios, self.reloj, self.ids, self.aleatorio)

    def cuenta(self, **datos: object) -> Cuenta:
        cuenta = Cuenta(
            self.ids.nuevo(),
            "ana@prueba.local",
            "Ana",
            activa=True,
            hash_contrasena="hash:clave-larga",
        )
        for campo, valor in datos.items():
            setattr(cuenta, campo, valor)
        self.cuentas.guardar(cuenta)
        return cuenta

    def cuenta_con_mfa(self) -> Cuenta:
        return self.cuenta(mfa_activo=True, mfa_secreto="SECRETO")
