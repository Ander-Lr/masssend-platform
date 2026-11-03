"""Usuario de la v1 con su token, compartido por las pruebas de campanas."""

from typing import Any

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from rest_framework_simplejwt.tokens import AccessToken

from masssend.domain.shared.identificadores import IdPublico
from masssend.infrastructure.composition.root import contenedor
from masssend.infrastructure.persistence.identidad.models import CuentaIdentidad

Usuario = get_user_model()
API = "/api/v1"


class Sesion:
    """Un usuario de la v1 con su token, listo para llamar a la API."""

    def __init__(self, nombre: str) -> None:
        self.usuario = Usuario.objects.create_user(
            f"{nombre}@prueba.local", password="clave-larga-123"
        )
        self.public_id: IdPublico = contenedor.generador_ids().nuevo()
        CuentaIdentidad.objects.create(usuario=self.usuario, public_id=self.public_id)
        token = AccessToken.for_user(self.usuario)
        token["public_id"] = str(self.public_id)
        self.cliente = Client(HTTP_AUTHORIZATION=f"Bearer {token}")

    def get(self, ruta: str = "", **params: Any) -> Any:
        return self.cliente.get(API + "/contactos" + ruta, params)

    def post(self, ruta: str = "", datos: Any = None) -> Any:
        return self.cliente.post(
            API + "/contactos" + ruta, datos or {}, content_type="application/json"
        )

    def patch(self, ruta: str, datos: Any) -> Any:
        return self.cliente.patch(API + "/contactos" + ruta, datos, content_type="application/json")

    def delete(self, ruta: str) -> Any:
        return self.cliente.delete(API + "/contactos" + ruta)

    def importar(self, contenido: str, nombre: str = "contactos.csv", **campos: Any) -> Any:
        archivo = SimpleUploadedFile(nombre, contenido.encode(), content_type="text/csv")
        return self.cliente.post(API + "/contactos/importar", {"archivo": archivo, **campos})

    def crear(self, telefono: str, **datos: Any) -> dict[str, Any]:
        respuesta = self.post(datos={"telefono": telefono, **datos})
        assert respuesta.status_code == 201, respuesta.content
        return dict(respuesta.json())

    def campanas(
        self, ruta: str = "", metodo: str = "get", datos: Any = None, **params: Any
    ) -> Any:
        url = API + "/campanas" + ruta
        if metodo == "get":
            return self.cliente.get(url, params)
        if metodo == "delete":
            return self.cliente.delete(url)
        return getattr(self.cliente, metodo)(url, datos or {}, content_type="application/json")

    def crear_campana(self, **datos: Any) -> dict[str, Any]:
        cuerpo = {"nombre": "Promo", "mensaje": "Hola {{nombre}}", **datos}
        respuesta = self.campanas(metodo="post", datos=cuerpo)
        assert respuesta.status_code == 201, respuesta.content
        return dict(respuesta.json())

    def subir(self, campana_id: str, nombre: str, contenido: bytes) -> Any:
        archivo = SimpleUploadedFile(nombre, contenido)
        return self.cliente.post(f"{API}/campanas/{campana_id}/adjunto", {"archivo": archivo})
