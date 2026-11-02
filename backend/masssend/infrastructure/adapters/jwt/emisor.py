from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from masssend.application.identidad.puertos import ParTokens
from masssend.domain.shared.errores import NoAutenticado
from masssend.domain.shared.identificadores import IdPublico, id_publico

Usuario = get_user_model()
TOKEN_INVALIDO = "El token no es válido."


class TokenAcceso(AccessToken):
    """Vida corta: tras revocar la renovacion, un acceso robado dura poco."""

    lifetime = timedelta(minutes=15)


class TokenRenovacion(RefreshToken):
    access_token_class = TokenAcceso


class EmisorSimpleJwt:
    def emitir(self, cuenta_id: IdPublico) -> ParTokens:
        usuario = Usuario.objects.get(cuenta_identidad__public_id=cuenta_id)
        renovacion = TokenRenovacion.for_user(usuario)
        renovacion["public_id"] = str(cuenta_id)
        return ParTokens(str(renovacion.access_token), str(renovacion))

    def renovar(self, renovacion: str) -> ParTokens:
        with transaction.atomic():
            token = self._leer(renovacion)
            cuenta_id = id_publico(str(token.get("public_id", "")))
            activa = Usuario.objects.filter(
                cuenta_identidad__public_id=cuenta_id, is_active=True
            ).exists()
            # blacklist() crea la fila una sola vez: en una carrera solo uno renueva.
            _, revocado_ahora = token.blacklist()
            if not activa or not revocado_ahora:
                raise NoAutenticado(TOKEN_INVALIDO)
            return self.emitir(cuenta_id)

    def revocar(self, renovacion: str) -> None:
        try:
            self._leer(renovacion).blacklist()
        except NoAutenticado:
            return

    def revocar_todos(self, cuenta_id: IdPublico) -> None:
        pendientes = OutstandingToken.objects.filter(
            user__cuenta_identidad__public_id=cuenta_id, blacklistedtoken__isnull=True
        )
        BlacklistedToken.objects.bulk_create(
            [BlacklistedToken(token=token) for token in pendientes], ignore_conflicts=True
        )

    @staticmethod
    def _leer(renovacion: str) -> TokenRenovacion:
        try:
            return TokenRenovacion(renovacion)
        except TokenError as error:
            raise NoAutenticado(TOKEN_INVALIDO) from error
