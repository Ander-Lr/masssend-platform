"""Registro y verificacion del correo."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from masssend.application.identidad.puertos import IColaCorreos, IHasherContrasenas
from masssend.application.shared.puertos import (
    IAleatorio,
    IGeneradorIds,
    IReloj,
    IUnidadDeTrabajo,
)
from masssend.domain.identidad.correo import normalizar_correo, validar_correo
from masssend.domain.identidad.cuenta import Cuenta
from masssend.domain.identidad.politicas import validar_contrasena
from masssend.domain.identidad.repositorios import IRepoCuentas
from masssend.domain.shared.errores import DatosInvalidos, EstadoInvalido
from masssend.domain.shared.identificadores import IdPublico

DIGITOS_CODIGO = 6
CODIGO_INCORRECTO = "El código es incorrecto."


@dataclass(frozen=True, slots=True)
class CuentaRegistrada:
    id: IdPublico
    correo: str
    codigo_expira_en: datetime


class RegistrarCuenta:
    def __init__(
        self,
        cuentas: IRepoCuentas,
        hasher: IHasherContrasenas,
        cola: IColaCorreos,
        uow: IUnidadDeTrabajo,
        reloj: IReloj,
        ids: IGeneradorIds,
        aleatorio: IAleatorio,
        vigencia_codigo: timedelta,
    ) -> None:
        self._cuentas = cuentas
        self._hasher = hasher
        self._cola = cola
        self._uow = uow
        self._reloj = reloj
        self._ids = ids
        self._aleatorio = aleatorio
        self._vigencia = vigencia_codigo

    def ejecutar(self, nombre: str, correo: str, contrasena: str) -> CuentaRegistrada:
        nombre_limpio = nombre.strip()
        if not nombre_limpio:
            raise DatosInvalidos("El nombre es obligatorio.", "nombre")
        correo_valido = validar_correo(correo)
        validar_contrasena(contrasena)
        hash_nuevo = self._hasher.generar(contrasena)
        codigo = self._aleatorio.digitos(DIGITOS_CODIGO)
        expira_en = self._reloj.ahora() + self._vigencia
        with self._uow:
            cuenta = self._cuentas.bloquear_por_correo(correo_valido)
            if cuenta is None:
                cuenta = Cuenta(self._ids.nuevo(), correo_valido, nombre_limpio)
            elif cuenta.activa:
                raise EstadoInvalido("La cuenta ya se encuentra activa.")
            cuenta.nombre = nombre_limpio
            cuenta.hash_contrasena = hash_nuevo
            cuenta.asignar_codigo(codigo, expira_en)
            self._cuentas.guardar(cuenta)
            self._cola.encolar_verificacion(nombre_limpio, correo_valido, codigo)
        return CuentaRegistrada(cuenta.id, correo_valido, expira_en)


class VerificarCuenta:
    def __init__(self, cuentas: IRepoCuentas, uow: IUnidadDeTrabajo, reloj: IReloj) -> None:
        self._cuentas = cuentas
        self._uow = uow
        self._reloj = reloj

    def ejecutar(self, correo: str, codigo: str) -> None:
        with self._uow:
            cuenta = self._cuentas.bloquear_por_correo(normalizar_correo(correo))
            if cuenta is None:
                raise DatosInvalidos(CODIGO_INCORRECTO, "codigo")
            correcto = cuenta.verificar(codigo.strip(), self._reloj.ahora())
            self._cuentas.guardar(cuenta)
        # Se lanza fuera de la transaccion: el intento fallido debe quedar guardado.
        if not correcto:
            raise DatosInvalidos(CODIGO_INCORRECTO, "codigo")


class ReenviarCodigo:
    """Responde igual exista o no la cuenta: no revela correos registrados."""

    def __init__(
        self,
        cuentas: IRepoCuentas,
        cola: IColaCorreos,
        uow: IUnidadDeTrabajo,
        reloj: IReloj,
        aleatorio: IAleatorio,
        vigencia_codigo: timedelta,
    ) -> None:
        self._cuentas = cuentas
        self._cola = cola
        self._uow = uow
        self._reloj = reloj
        self._aleatorio = aleatorio
        self._vigencia = vigencia_codigo

    def ejecutar(self, correo: str) -> None:
        with self._uow:
            cuenta = self._cuentas.bloquear_por_correo(normalizar_correo(correo))
            if cuenta is None or cuenta.activa:
                return
            codigo = self._aleatorio.digitos(DIGITOS_CODIGO)
            cuenta.asignar_codigo(codigo, self._reloj.ahora() + self._vigencia)
            self._cuentas.guardar(cuenta)
            self._cola.encolar_verificacion(cuenta.nombre, cuenta.correo, codigo)
