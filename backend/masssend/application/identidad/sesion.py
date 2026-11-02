"""Inicio de sesion en dos pasos y ciclo de vida de los tokens."""

from dataclasses import dataclass
from datetime import datetime

from masssend.application.identidad.desafios import ServicioDesafios
from masssend.application.identidad.puertos import (
    IEmisorTokens,
    IHasherContrasenas,
    ITotp,
    ParTokens,
)
from masssend.application.shared.puertos import IReloj, IUnidadDeTrabajo
from masssend.domain.identidad.cuenta import Cuenta
from masssend.domain.identidad.desafio import Proposito
from masssend.domain.identidad.politicas import (
    VIGENCIA_DESAFIO_ENROLAMIENTO,
    VIGENCIA_DESAFIO_LOGIN,
)
from masssend.domain.identidad.repositorios import IRepoCuentas
from masssend.domain.shared.errores import NoAutenticado
from masssend.domain.shared.identificadores import IdPublico

CREDENCIALES_INCORRECTAS = "Correo o contraseña incorrectos."
CODIGO_INCORRECTO = "El código no es válido."


@dataclass(frozen=True, slots=True)
class SiguientePaso:
    siguiente: str
    token_desafio: str
    expira_en: datetime


def emitir_siguiente_paso(cuenta: Cuenta, desafios: ServicioDesafios) -> SiguientePaso:
    """La contrasena nunca entrega tokens: siempre falta el doble factor."""
    if cuenta.mfa_activo:
        desafio = desafios.emitir(Proposito.TOTP, VIGENCIA_DESAFIO_LOGIN, cuenta.id)
        return SiguientePaso("totp", desafio.token, desafio.expira_en)
    desafio = desafios.emitir(Proposito.ENROLAMIENTO, VIGENCIA_DESAFIO_ENROLAMIENTO, cuenta.id)
    return SiguientePaso("activar_mfa", desafio.token, desafio.expira_en)


class IniciarSesion:
    def __init__(
        self,
        cuentas: IRepoCuentas,
        hasher: IHasherContrasenas,
        desafios: ServicioDesafios,
        uow: IUnidadDeTrabajo,
    ) -> None:
        self._cuentas = cuentas
        self._hasher = hasher
        self._desafios = desafios
        self._uow = uow

    def ejecutar(self, identificador: str, contrasena: str) -> SiguientePaso:
        cuenta = self._cuentas.buscar_por_correo(identificador)
        correcta = self._hasher.verificar(contrasena, cuenta.hash_contrasena if cuenta else None)
        if cuenta is None or not correcta or not cuenta.activa:
            raise NoAutenticado(CREDENCIALES_INCORRECTAS)
        with self._uow:
            return emitir_siguiente_paso(cuenta, self._desafios)


class ValidarTotp:
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

    def ejecutar(self, token_desafio: str, codigo: str) -> ParTokens:
        ahora = self._reloj.ahora()
        resultado: ParTokens | None = None
        with self._uow:
            desafio = self._desafios.exigir(token_desafio, Proposito.TOTP)
            if desafio.cuenta_id is None:
                raise NoAutenticado(CODIGO_INCORRECTO)
            cuenta = self._cuentas.bloquear(desafio.cuenta_id)
            cuenta.exigir_sin_bloqueo(ahora)
            paso = self._totp.paso_valido(cuenta.mfa_secreto or "", codigo, ahora)
            if cuenta.validar_paso_totp(paso, ahora):
                self._desafios.consumir(desafio)
                resultado = self._tokens.emitir(cuenta.id)
            self._cuentas.guardar(cuenta)
        # Fuera de la transaccion: el fallo debe contar para el bloqueo.
        if resultado is None:
            raise NoAutenticado(CODIGO_INCORRECTO)
        return resultado


@dataclass(frozen=True, slots=True)
class Perfil:
    id: str
    nombre: str
    correo: str
    mfa_activo: bool
    es_staff: bool


class ConsultarPerfil:
    def __init__(self, cuentas: IRepoCuentas) -> None:
        self._cuentas = cuentas

    def ejecutar(self, cuenta_id: IdPublico) -> Perfil:
        cuenta = self._cuentas.obtener(cuenta_id)
        return Perfil(
            str(cuenta.id), cuenta.nombre, cuenta.correo, cuenta.mfa_activo, cuenta.es_staff
        )


class RenovarToken:
    def __init__(self, tokens: IEmisorTokens) -> None:
        self._tokens = tokens

    def ejecutar(self, renovacion: str) -> ParTokens:
        return self._tokens.renovar(renovacion)


class CerrarSesion:
    def __init__(self, tokens: IEmisorTokens) -> None:
        self._tokens = tokens

    def ejecutar(self, renovacion: str) -> None:
        self._tokens.revocar(renovacion)
