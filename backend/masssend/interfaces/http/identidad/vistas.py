"""Vistas delgadas: validan el formato, llaman al caso de uso y responden."""

from dataclasses import asdict
from typing import Any

from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from masssend.application.identidad.puertos import ParTokens
from masssend.application.identidad.sesion import SiguientePaso
from masssend.infrastructure.composition.identidad import contenedor_identidad as identidad
from masssend.interfaces.http.identidad import serializadores as s
from masssend.interfaces.http.shared.limites import LimiteSensible
from masssend.interfaces.http.shared.vistas import VistaApi, cuenta_actual

SOLICITUD_RECIBIDA = {"detalle": "Si la cuenta aplica, recibirás un correo."}


def validar(clase: type[serializers.Serializer], datos: Any) -> dict[str, Any]:
    entrada = clase(data=datos)
    entrada.is_valid(raise_exception=True)
    return dict(entrada.validated_data)


def respuesta_tokens(par: ParTokens) -> Response:
    return Response({"acceso": par.acceso, "renovacion": par.renovacion, "tipo": "Bearer"})


def respuesta_paso(paso: SiguientePaso) -> Response:
    return Response(
        {
            "siguiente": paso.siguiente,
            "token_desafio": paso.token_desafio,
            "expira_en": paso.expira_en.isoformat(),
        }
    )


class VistaPublica(VistaApi):
    authentication_classes: list[Any] = []
    permission_classes = [AllowAny]
    throttle_classes = [LimiteSensible]


class VistaSensible(VistaApi):
    throttle_classes = [LimiteSensible]


class RegistroVista(VistaPublica):
    def post(self, request: Request) -> Response:
        datos = validar(s.Registro, request.data)
        creada = identidad.registrar().ejecutar(
            datos["nombre"], datos["correo"], datos["contrasena"]
        )
        return Response(
            {
                "id": str(creada.id),
                "correo": creada.correo,
                "codigo_expira_en": creada.codigo_expira_en.isoformat(),
            },
            status=201,
        )


class VerificarVista(VistaPublica):
    def post(self, request: Request) -> Response:
        datos = validar(s.Verificar, request.data)
        identidad.verificar().ejecutar(datos["correo"], datos["codigo"])
        return Response({"detalle": "La cuenta quedó activa."})


class ReenviarCodigoVista(VistaPublica):
    def post(self, request: Request) -> Response:
        identidad.reenviar().ejecutar(validar(s.Correo, request.data)["correo"])
        return Response(SOLICITUD_RECIBIDA, status=202)


class LoginVista(VistaPublica):
    def post(self, request: Request) -> Response:
        datos = validar(s.Login, request.data)
        return respuesta_paso(
            identidad.iniciar_sesion().ejecutar(datos["correo"], datos["contrasena"])
        )


class LoginTotpVista(VistaPublica):
    def post(self, request: Request) -> Response:
        datos = validar(s.LoginTotp, request.data)
        return respuesta_tokens(
            identidad.validar_totp().ejecutar(datos["token_desafio"], datos["codigo"])
        )


class RenovarVista(VistaPublica):
    def post(self, request: Request) -> Response:
        renovacion = validar(s.Renovacion, request.data)["renovacion"]
        return respuesta_tokens(identidad.renovar().ejecutar(renovacion))


class LogoutVista(VistaApi):
    def post(self, request: Request) -> Response:
        identidad.cerrar_sesion().ejecutar(validar(s.Renovacion, request.data)["renovacion"])
        return Response(status=204)


class YoVista(VistaApi):
    def get(self, request: Request) -> Response:
        return Response(asdict(identidad.perfil().ejecutar(cuenta_actual(request))))


class GoogleVista(VistaPublica):
    def get(self, request: Request) -> Response:
        return Response({"url": identidad.iniciar_google().ejecutar()})


class GoogleCallbackVista(VistaPublica):
    def get(self, request: Request) -> Response:
        datos = validar(s.GoogleCallback, request.query_params)
        return respuesta_paso(
            identidad.completar_google().ejecutar(datos["state"], datos["code"])
        )


class RecuperarVista(VistaPublica):
    def post(self, request: Request) -> Response:
        identidad.solicitar_recuperacion().ejecutar(validar(s.Correo, request.data)["correo"])
        return Response(SOLICITUD_RECIBIDA, status=202)


class RestablecerVista(VistaPublica):
    def post(self, request: Request) -> Response:
        datos = validar(s.Restablecer, request.data)
        identidad.restablecer().ejecutar(datos["token"], datos["nueva_contrasena"])
        return Response({"detalle": "La contraseña se actualizó."})


class CambiarContrasenaVista(VistaSensible):
    def post(self, request: Request) -> Response:
        datos = validar(s.CambiarContrasena, request.data)
        identidad.cambiar_contrasena().ejecutar(
            cuenta_actual(request), datos["contrasena_actual"], datos["nueva_contrasena"]
        )
        return Response({"detalle": "La contraseña se actualizó."})


class VistaMfa(VistaApi):
    """Acepta JWT o, durante el enrolamiento, el token de desafio."""

    permission_classes = [AllowAny]
    throttle_classes = [LimiteSensible]

    @staticmethod
    def resolver(request: Request, token_desafio: str | None) -> Any:
        if token_desafio:
            return identidad.resolver_enrolamiento().ejecutar(token_desafio)
        return cuenta_actual(request)


class MfaActivarVista(VistaMfa):
    def post(self, request: Request) -> Response:
        datos = validar(s.ActivarMfa, request.data)
        cuenta_id = self.resolver(request, datos.get("token_desafio"))
        return Response(asdict(identidad.activar_mfa().ejecutar(cuenta_id)))


class MfaConfirmarVista(VistaMfa):
    def post(self, request: Request) -> Response:
        datos = validar(s.ConfirmarMfa, request.data)
        token = datos.get("token_desafio")
        par = identidad.confirmar_mfa().ejecutar(
            self.resolver(request, token), datos["codigo"], token
        )
        return respuesta_tokens(par) if par else Response({"activo": True})


class MfaEstadoVista(VistaApi):
    def get(self, request: Request) -> Response:
        return Response({"activo": identidad.estado_mfa().ejecutar(cuenta_actual(request))})


class MfaDesactivarVista(VistaSensible):
    def post(self, request: Request) -> Response:
        datos = validar(s.DesactivarMfa, request.data)
        identidad.desactivar_mfa().ejecutar(cuenta_actual(request), datos["contrasena"])
        return Response({"activo": False})
