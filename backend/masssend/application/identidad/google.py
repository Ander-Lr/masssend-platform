"""Acceso con Google. Google reemplaza la contrasena, no el doble factor."""

from masssend.application.identidad.desafios import ServicioDesafios
from masssend.application.identidad.puertos import IProveedorGoogle
from masssend.application.identidad.sesion import SiguientePaso, emitir_siguiente_paso
from masssend.application.shared.puertos import IGeneradorIds, IUnidadDeTrabajo
from masssend.domain.identidad.correo import validar_correo
from masssend.domain.identidad.cuenta import Cuenta
from masssend.domain.identidad.desafio import Proposito
from masssend.domain.identidad.politicas import VIGENCIA_ESTADO_GOOGLE
from masssend.domain.identidad.repositorios import IRepoCuentas
from masssend.domain.shared.errores import NoAutenticado


class IniciarGoogle:
    def __init__(
        self,
        proveedor: IProveedorGoogle,
        desafios: ServicioDesafios,
        uow: IUnidadDeTrabajo,
    ) -> None:
        self._proveedor = proveedor
        self._desafios = desafios
        self._uow = uow

    def ejecutar(self) -> str:
        with self._uow:
            estado = self._desafios.emitir(Proposito.GOOGLE, VIGENCIA_ESTADO_GOOGLE)
        return self._proveedor.url_autorizacion(estado.token)


class CompletarGoogle:
    def __init__(
        self,
        cuentas: IRepoCuentas,
        proveedor: IProveedorGoogle,
        desafios: ServicioDesafios,
        uow: IUnidadDeTrabajo,
        ids: IGeneradorIds,
    ) -> None:
        self._cuentas = cuentas
        self._proveedor = proveedor
        self._desafios = desafios
        self._uow = uow
        self._ids = ids

    def ejecutar(self, estado: str, codigo: str) -> SiguientePaso:
        with self._uow:
            self._desafios.consumir(self._desafios.exigir(estado, Proposito.GOOGLE))
        # La llamada a Google queda fuera de toda transaccion.
        perfil = self._proveedor.perfil(codigo)
        if not perfil.verificado:
            raise NoAutenticado("Google no verificó este correo.")
        correo = validar_correo(perfil.correo)
        with self._uow:
            cuenta = self._cuentas.bloquear_por_correo(correo)
            if cuenta is None:
                cuenta = Cuenta(self._ids.nuevo(), correo, perfil.nombre or correo)
            cuenta.activar_por_google()
            self._cuentas.guardar(cuenta)
            return emitir_siguiente_paso(cuenta, self._desafios)
