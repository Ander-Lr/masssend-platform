import logging
from urllib.parse import urlencode

import requests

from masssend.application.identidad.puertos import PerfilGoogle
from masssend.domain.shared.errores import ServicioNoDisponible

logger = logging.getLogger(__name__)

URL_AUTORIZACION = "https://accounts.google.com/o/oauth2/v2/auth"
URL_TOKEN = "https://oauth2.googleapis.com/token"
URL_PERFIL = "https://www.googleapis.com/oauth2/v2/userinfo"
ALCANCES = "openid email profile"


class ProveedorGoogleOauth:
    def __init__(self, cliente_id: str, cliente_secreto: str, url_retorno: str) -> None:
        self._cliente_id = cliente_id
        self._cliente_secreto = cliente_secreto
        self._url_retorno = url_retorno

    def url_autorizacion(self, estado: str) -> str:
        parametros = {
            "client_id": self._cliente_id,
            "redirect_uri": self._url_retorno,
            "response_type": "code",
            "scope": ALCANCES,
            "state": estado,
            "prompt": "select_account",
        }
        return f"{URL_AUTORIZACION}?{urlencode(parametros)}"

    def perfil(self, codigo: str) -> PerfilGoogle:
        try:
            token = requests.post(
                URL_TOKEN,
                data={
                    "code": codigo,
                    "client_id": self._cliente_id,
                    "client_secret": self._cliente_secreto,
                    "redirect_uri": self._url_retorno,
                    "grant_type": "authorization_code",
                },
                timeout=10,
            )
            token.raise_for_status()
            perfil = requests.get(
                URL_PERFIL,
                headers={"Authorization": f"Bearer {token.json()['access_token']}"},
                timeout=10,
            )
            perfil.raise_for_status()
            datos = perfil.json()
        except (requests.RequestException, KeyError, ValueError) as error:
            logger.warning("Google no respondio: %s", type(error).__name__)
            raise ServicioNoDisponible("Google no está disponible.") from error
        return PerfilGoogle(
            correo=datos.get("email", ""),
            nombre=datos.get("name", ""),
            verificado=bool(datos.get("verified_email")),
        )
