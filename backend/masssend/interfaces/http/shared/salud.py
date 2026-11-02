from dataclasses import asdict

from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from masssend.infrastructure.composition.root import contenedor
from masssend.interfaces.http.shared.vistas import VistaApi


class SaludVista(VistaApi):
    """Publica y sin limite, para que un monitor pueda consultarla siempre."""

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = []

    def get(self, request: Request) -> Response:
        resultado = contenedor.comprobar_salud().ejecutar()
        return Response(asdict(resultado), status=200 if resultado.disponible else 503)
