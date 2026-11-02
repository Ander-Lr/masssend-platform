"""Recuperacion y cambio de contrasena."""

from masssend.application.identidad.desafios import ServicioDesafios
from masssend.application.identidad.puertos import (
    IColaCorreos,
    IEmisorTokens,
    IHasherContrasenas,
)
from masssend.application.shared.puertos import IUnidadDeTrabajo
from masssend.domain.identidad.correo import normalizar_correo
from masssend.domain.identidad.desafio import Proposito
from masssend.domain.identidad.politicas import VIGENCIA_RECUPERACION, validar_contrasena
from masssend.domain.identidad.repositorios import IRepoCuentas, IRepoDesafios
from masssend.domain.shared.errores import DatosInvalidos, NoAutenticado
from masssend.domain.shared.identificadores import IdPublico


class SolicitarRecuperacion:
    """Responde igual exista o no la cuenta: no revela correos registrados."""

    def __init__(
        self,
        cuentas: IRepoCuentas,
        repo_desafios: IRepoDesafios,
        desafios: ServicioDesafios,
        cola: IColaCorreos,
        uow: IUnidadDeTrabajo,
    ) -> None:
        self._cuentas = cuentas
        self._repo_desafios = repo_desafios
        self._desafios = desafios
        self._cola = cola
        self._uow = uow

    def ejecutar(self, correo: str) -> None:
        with self._uow:
            cuenta = self._cuentas.buscar_por_correo(normalizar_correo(correo))
            if cuenta is None or not cuenta.activa:
                return
            self._repo_desafios.anular_pendientes(cuenta.id, Proposito.RECUPERACION)
            desafio = self._desafios.emitir(
                Proposito.RECUPERACION, VIGENCIA_RECUPERACION, cuenta.id
            )
            minutos = int(VIGENCIA_RECUPERACION.total_seconds() // 60)
            self._cola.encolar_recuperacion(cuenta.nombre, cuenta.correo, desafio.token, minutos)


class RestablecerContrasena:
    def __init__(
        self,
        cuentas: IRepoCuentas,
        desafios: ServicioDesafios,
        hasher: IHasherContrasenas,
        tokens: IEmisorTokens,
        uow: IUnidadDeTrabajo,
    ) -> None:
        self._cuentas = cuentas
        self._desafios = desafios
        self._hasher = hasher
        self._tokens = tokens
        self._uow = uow

    def ejecutar(self, token: str, nueva: str) -> None:
        validar_contrasena(nueva, "nueva_contrasena")
        hash_nuevo = self._hasher.generar(nueva)
        with self._uow:
            desafio = self._desafios.exigir(token, Proposito.RECUPERACION)
            if desafio.cuenta_id is None:
                raise NoAutenticado("El desafío no es válido o venció.")
            cuenta = self._cuentas.bloquear(desafio.cuenta_id)
            cuenta.hash_contrasena = hash_nuevo
            self._cuentas.guardar(cuenta)
            self._desafios.consumir(desafio)
            self._tokens.revocar_todos(cuenta.id)


class CambiarContrasena:
    def __init__(
        self,
        cuentas: IRepoCuentas,
        hasher: IHasherContrasenas,
        tokens: IEmisorTokens,
        uow: IUnidadDeTrabajo,
    ) -> None:
        self._cuentas = cuentas
        self._hasher = hasher
        self._tokens = tokens
        self._uow = uow

    def ejecutar(self, cuenta_id: IdPublico, actual: str, nueva: str) -> None:
        validar_contrasena(nueva, "nueva_contrasena")
        hash_nuevo = self._hasher.generar(nueva)
        with self._uow:
            cuenta = self._cuentas.bloquear(cuenta_id)
            if not self._hasher.verificar(actual, cuenta.hash_contrasena):
                raise DatosInvalidos("La contraseña actual es incorrecta.", "contrasena_actual")
            cuenta.hash_contrasena = hash_nuevo
            self._cuentas.guardar(cuenta)
            self._tokens.revocar_todos(cuenta.id)
