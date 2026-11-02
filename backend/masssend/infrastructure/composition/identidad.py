"""Contenedor del modulo de identidad."""

from datetime import timedelta

from django.conf import settings

from masssend.application.identidad.desafios import ServicioDesafios
from masssend.application.identidad.google import CompletarGoogle, IniciarGoogle
from masssend.application.identidad.mfa import (
    ActivarMfa,
    ConfirmarMfa,
    ConsultarMfa,
    DesactivarMfa,
    ResolverCuentaEnrolamiento,
)
from masssend.application.identidad.puertos import IProveedorGoogle
from masssend.application.identidad.recuperacion import (
    CambiarContrasena,
    RestablecerContrasena,
    SolicitarRecuperacion,
)
from masssend.application.identidad.registro import (
    ReenviarCodigo,
    RegistrarCuenta,
    VerificarCuenta,
)
from masssend.application.identidad.sesion import (
    CerrarSesion,
    ConsultarPerfil,
    IniciarSesion,
    RenovarToken,
    ValidarTotp,
)
from masssend.infrastructure.adapters.correo.cola import ColaEmailTask
from masssend.infrastructure.adapters.google.falso import ProveedorGoogleFalso
from masssend.infrastructure.adapters.google.oauth import ProveedorGoogleOauth
from masssend.infrastructure.adapters.jwt.emisor import EmisorSimpleJwt
from masssend.infrastructure.adapters.sistema.contrasenas import HasherDjango
from masssend.infrastructure.adapters.totp.motor import TotpPyotp
from masssend.infrastructure.composition.root import contenedor as raiz
from masssend.infrastructure.persistence.identidad.repositorios import (
    RepoCuentasDjango,
    RepoDesafiosDjango,
)


class ContenedorIdentidad:
    def _cuentas(self) -> RepoCuentasDjango:
        return RepoCuentasDjango(raiz.generador_ids())

    def _desafios(self) -> ServicioDesafios:
        return ServicioDesafios(
            RepoDesafiosDjango(), raiz.reloj(), raiz.generador_ids(), raiz.aleatorio()
        )

    def _totp(self) -> TotpPyotp:
        return TotpPyotp(settings.MFA_ISSUER, settings.MFA_WINDOW)

    def _cola(self) -> ColaEmailTask:
        return ColaEmailTask(settings.FRONTEND_URL)

    def _vigencia_codigo(self) -> timedelta:
        return timedelta(minutes=settings.EMAIL_CODE_TTL_MINUTES)

    def _google(self) -> IProveedorGoogle:
        if settings.PROVEEDOR_GOOGLE == "fake":
            return ProveedorGoogleFalso()
        return ProveedorGoogleOauth(
            settings.GOOGLE_CLIENT_ID, settings.GOOGLE_CLIENT_SECRET, settings.GOOGLE_RETORNO_V1
        )

    def registrar(self) -> RegistrarCuenta:
        return RegistrarCuenta(
            self._cuentas(),
            HasherDjango(),
            self._cola(),
            raiz.unidad_de_trabajo(),
            raiz.reloj(),
            raiz.generador_ids(),
            raiz.aleatorio(),
            self._vigencia_codigo(),
        )

    def verificar(self) -> VerificarCuenta:
        return VerificarCuenta(self._cuentas(), raiz.unidad_de_trabajo(), raiz.reloj())

    def reenviar(self) -> ReenviarCodigo:
        return ReenviarCodigo(
            self._cuentas(),
            self._cola(),
            raiz.unidad_de_trabajo(),
            raiz.reloj(),
            raiz.aleatorio(),
            self._vigencia_codigo(),
        )

    def iniciar_sesion(self) -> IniciarSesion:
        return IniciarSesion(
            self._cuentas(), HasherDjango(), self._desafios(), raiz.unidad_de_trabajo()
        )

    def validar_totp(self) -> ValidarTotp:
        return ValidarTotp(
            self._cuentas(),
            self._desafios(),
            self._totp(),
            EmisorSimpleJwt(),
            raiz.unidad_de_trabajo(),
            raiz.reloj(),
        )

    def renovar(self) -> RenovarToken:
        return RenovarToken(EmisorSimpleJwt())

    def cerrar_sesion(self) -> CerrarSesion:
        return CerrarSesion(EmisorSimpleJwt())

    def perfil(self) -> ConsultarPerfil:
        return ConsultarPerfil(self._cuentas())

    def resolver_enrolamiento(self) -> ResolverCuentaEnrolamiento:
        return ResolverCuentaEnrolamiento(self._desafios(), raiz.unidad_de_trabajo())

    def activar_mfa(self) -> ActivarMfa:
        return ActivarMfa(self._cuentas(), self._totp(), raiz.unidad_de_trabajo())

    def confirmar_mfa(self) -> ConfirmarMfa:
        return ConfirmarMfa(
            self._cuentas(),
            self._desafios(),
            self._totp(),
            EmisorSimpleJwt(),
            raiz.unidad_de_trabajo(),
            raiz.reloj(),
        )

    def estado_mfa(self) -> ConsultarMfa:
        return ConsultarMfa(self._cuentas())

    def desactivar_mfa(self) -> DesactivarMfa:
        return DesactivarMfa(self._cuentas(), HasherDjango(), raiz.unidad_de_trabajo())

    def solicitar_recuperacion(self) -> SolicitarRecuperacion:
        return SolicitarRecuperacion(
            self._cuentas(),
            RepoDesafiosDjango(),
            self._desafios(),
            self._cola(),
            raiz.unidad_de_trabajo(),
        )

    def restablecer(self) -> RestablecerContrasena:
        return RestablecerContrasena(
            self._cuentas(),
            self._desafios(),
            HasherDjango(),
            EmisorSimpleJwt(),
            raiz.unidad_de_trabajo(),
        )

    def cambiar_contrasena(self) -> CambiarContrasena:
        return CambiarContrasena(
            self._cuentas(), HasherDjango(), EmisorSimpleJwt(), raiz.unidad_de_trabajo()
        )

    def iniciar_google(self) -> IniciarGoogle:
        return IniciarGoogle(self._google(), self._desafios(), raiz.unidad_de_trabajo())

    def completar_google(self) -> CompletarGoogle:
        return CompletarGoogle(
            self._cuentas(),
            self._google(),
            self._desafios(),
            raiz.unidad_de_trabajo(),
            raiz.generador_ids(),
        )


contenedor_identidad = ContenedorIdentidad()
