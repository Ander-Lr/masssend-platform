"""Activacion y desactivacion del doble factor."""

from dataclasses import dataclass

from masssend.application.identidad.desafios import ServicioDesafios
from masssend.application.identidad.puertos import (
    IEmisorTokens,
    IHasherContrasenas,
    ITotp,
    ParTokens,
)
from masssend.application.shared.puertos import IReloj, IUnidadDeTrabajo
from masssend.domain.identidad.desafio import Proposito
from masssend.domain.identidad.repositorios import IRepoCuentas
from masssend.domain.shared.errores import DatosInvalidos, EstadoInvalido
from masssend.domain.shared.identificadores import IdPublico


@dataclass(frozen=True, slots=True)
class MfaIniciado:
    clave_manual: str
    uri: str
    qr: str


class ResolverCuentaEnrolamiento:
    """Quien aun no tiene doble factor no tiene JWT: se identifica con su desafio."""

    def __init__(self, desafios: ServicioDesafios, uow: IUnidadDeTrabajo) -> None:
        self._desafios = desafios
        self._uow = uow

    def ejecutar(self, token_desafio: str) -> IdPublico:
        with self._uow:
            desafio = self._desafios.exigir(token_desafio, Proposito.ENROLAMIENTO)
        if desafio.cuenta_id is None:
            raise EstadoInvalido("El desafío no pertenece a una cuenta.")
        return desafio.cuenta_id


class ActivarMfa:
    def __init__(self, cuentas: IRepoCuentas, totp: ITotp, uow: IUnidadDeTrabajo) -> None:
        self._cuentas = cuentas
        self._totp = totp
        self._uow = uow

    def ejecutar(self, cuenta_id: IdPublico) -> MfaIniciado:
        secreto = self._totp.generar_secreto()
        with self._uow:
            cuenta = self._cuentas.bloquear(cuenta_id)
            cuenta.iniciar_mfa(secreto)
            self._cuentas.guardar(cuenta)
        uri = self._totp.uri(secreto, cuenta.correo)
        return MfaIniciado(secreto, uri, self._totp.qr(uri))


class ConfirmarMfa:
    def __init__(
        self,
        cuentas: IRepoCuentas,
        desafios: ServicioDesafios,
        totp: ITotp,
        tokens: IEmisorTokens,
        uow: IUnidadDeTrabajo,
        reloj: IReloj,
    ) -> None:
        self._cuentas = cuentas
        self._desafios = desafios
        self._totp = totp
        self._tokens = tokens
        self._uow = uow
        self._reloj = reloj

    def ejecutar(
        self, cuenta_id: IdPublico, codigo: str, token_desafio: str | None = None
    ) -> ParTokens | None:
        """Con desafio termina el enrolamiento y entrega los tokens."""
        with self._uow:
            desafio = (
                self._desafios.exigir(token_desafio, Proposito.ENROLAMIENTO)
                if token_desafio
                else None
            )
            cuenta = self._cuentas.bloquear(cuenta_id)
            if cuenta.mfa_activo:
                raise EstadoInvalido("El doble factor ya está activo.")
            if not cuenta.mfa_secreto_pendiente:
                raise EstadoInvalido("No hay una activación pendiente.")
            paso = self._totp.paso_valido(
                cuenta.mfa_secreto_pendiente, codigo, self._reloj.ahora()
            )
            if paso is None:
                raise DatosInvalidos("El código no es válido.", "codigo")
            cuenta.confirmar_mfa(paso)
            self._cuentas.guardar(cuenta)
            if desafio is None:
                return None
            self._desafios.consumir(desafio)
            return self._tokens.emitir(cuenta.id)


class ConsultarMfa:
    def __init__(self, cuentas: IRepoCuentas) -> None:
        self._cuentas = cuentas

    def ejecutar(self, cuenta_id: IdPublico) -> bool:
        return self._cuentas.obtener(cuenta_id).mfa_activo


class DesactivarMfa:
    def __init__(
        self, cuentas: IRepoCuentas, hasher: IHasherContrasenas, uow: IUnidadDeTrabajo
    ) -> None:
        self._cuentas = cuentas
        self._hasher = hasher
        self._uow = uow

    def ejecutar(self, cuenta_id: IdPublico, contrasena: str) -> None:
        with self._uow:
            cuenta = self._cuentas.bloquear(cuenta_id)
            if not self._hasher.verificar(contrasena, cuenta.hash_contrasena):
                raise DatosInvalidos("La contraseña es incorrecta.", "contrasena")
            cuenta.desactivar_mfa()
            self._cuentas.guardar(cuenta)
