"""Contactos contra PostgreSQL: API v1, aislamiento entre duenos e importacion por lotes."""

from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from rest_framework_simplejwt.tokens import AccessToken

from mass_sender.models import Contact
from masssend.domain.campanas.repositorios import FiltroContactos
from masssend.domain.shared.identificadores import IdPublico, id_publico
from masssend.domain.shared.paginacion import PeticionPagina
from masssend.infrastructure.composition.campanas import contenedor_campanas
from masssend.infrastructure.composition.root import contenedor
from masssend.infrastructure.persistence.campanas.models import ContactoFila
from masssend.infrastructure.persistence.identidad.models import CuentaIdentidad

pytestmark = pytest.mark.django_db
Usuario = get_user_model()
API = "/api/v1/contactos"


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
        return self.cliente.get(API + ruta, params)

    def post(self, ruta: str = "", datos: Any = None) -> Any:
        return self.cliente.post(API + ruta, datos or {}, content_type="application/json")

    def patch(self, ruta: str, datos: Any) -> Any:
        return self.cliente.patch(API + ruta, datos, content_type="application/json")

    def delete(self, ruta: str) -> Any:
        return self.cliente.delete(API + ruta)

    def importar(self, contenido: str, nombre: str = "contactos.csv", **campos: Any) -> Any:
        archivo = SimpleUploadedFile(nombre, contenido.encode(), content_type="text/csv")
        return self.cliente.post(API + "/importar", {"archivo": archivo, **campos})

    def crear(self, telefono: str, **datos: Any) -> dict[str, Any]:
        respuesta = self.post(datos={"telefono": telefono, **datos})
        assert respuesta.status_code == 201, respuesta.content
        return dict(respuesta.json())


@pytest.fixture
def ana() -> Sesion:
    return Sesion("ana")


@pytest.fixture
def luis() -> Sesion:
    return Sesion("luis")


def test_crear_normaliza_y_responde_uuidv7(ana: Sesion) -> None:
    creado = ana.crear("099 111-2222", nombre="Pedro", etiquetas=["vip", "cliente"])
    assert id_publico(creado["id"])
    assert creado["telefono"] == "593991112222"
    assert creado["etiquetas"] == ["vip", "cliente"]
    fila = Contact.objects.get(phone_number="593991112222")
    assert fila.owner == ana.usuario
    assert fila.tags == "vip,cliente"


def test_el_mismo_numero_actualiza_y_responde_200(ana: Sesion) -> None:
    creado = ana.crear("0991112222", nombre="Pedro")
    repetido = ana.post(datos={"telefono": "+593991112222", "nombre": "Pedro P"})
    assert repetido.status_code == 200
    assert repetido.json()["id"] == creado["id"]
    assert Contact.objects.count() == 1


def test_un_telefono_invalido_responde_422_con_el_campo(ana: Sesion) -> None:
    respuesta = ana.post(datos={"telefono": "022345678"})
    assert respuesta.status_code == 422
    assert respuesta["Content-Type"] == "application/problem+json"
    assert respuesta.json()["campo"] == "telefono"


def test_sin_token_responde_401() -> None:
    assert Client().get(API).status_code == 401


def test_un_contacto_ajeno_responde_404(ana: Sesion, luis: Sesion) -> None:
    creado = ana.crear("0991112222", nombre="Pedro")
    ruta = "/" + creado["id"]
    assert luis.get(ruta).status_code == 404
    assert luis.patch(ruta, {"nombre": "Robado"}).status_code == 404
    assert luis.delete(ruta).status_code == 404
    assert luis.get().json()["datos"] == []
    assert ana.get(ruta).json()["nombre"] == "Pedro"


def test_dos_duenos_pueden_tener_el_mismo_numero(ana: Sesion, luis: Sesion) -> None:
    ana.crear("0991112222")
    luis.crear("0991112222")
    assert Contact.objects.filter(phone_number="593991112222").count() == 2


def test_un_id_mal_formado_responde_404(ana: Sesion) -> None:
    assert ana.get("/no-es-un-id").status_code == 404


def test_editar_y_dar_de_baja(ana: Sesion) -> None:
    creado = ana.crear("0991112222", nombre="Pedro", etiquetas="vip")
    respuesta = ana.patch(
        "/" + creado["id"],
        {"etiquetas": "lead, vip", "datos": {"ciudad": "Quito"}, "dado_de_baja": True},
    )
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert (cuerpo["nombre"], cuerpo["etiquetas"]) == ("Pedro", ["lead", "vip"])
    fila = Contact.objects.get()
    assert fila.is_opted_out
    assert fila.custom_data == {"ciudad": "Quito"}


def test_editar_con_datos_invalidos_responde_422(ana: Sesion) -> None:
    creado = ana.crear("0991112222")
    respuesta = ana.patch("/" + creado["id"], {"etiquetas": 5})
    assert respuesta.status_code == 422


def test_eliminar(ana: Sesion) -> None:
    creado = ana.crear("0991112222")
    assert ana.delete("/" + creado["id"]).status_code == 204
    assert ana.get("/" + creado["id"]).status_code == 404
    assert not Contact.objects.exists()


def test_eliminar_lote_solo_cuenta_los_propios(ana: Sesion, luis: Sesion) -> None:
    propios = [ana.crear(f"099111111{i}")["id"] for i in range(3)]
    ajeno = luis.crear("0992222222")["id"]
    respuesta = ana.post("/eliminar-lote", {"ids": [*propios, ajeno]})
    assert respuesta.json() == {"eliminados": 3}
    assert Contact.objects.count() == 1


def test_eliminar_lote_rechaza_ids_invalidos(ana: Sesion) -> None:
    assert ana.post("/eliminar-lote", {"ids": ["abc"]}).status_code == 422
    assert ana.post("/eliminar-lote", {"ids": []}).status_code == 422


def test_listar_pagina_y_filtra_con_pocas_consultas(ana: Sesion, luis: Sesion) -> None:
    for i in range(5):
        ana.crear(f"099111111{i}", nombre=f"Cliente {i}", etiquetas="vip" if i % 2 else "lead")
    luis.crear("0992222222", etiquetas="vip")
    with CaptureQueriesContext(connection) as consultas:
        listar = contenedor_campanas.listar_contactos()
        listar.ejecutar(ana.public_id, FiltroContactos(etiqueta="vip"), PeticionPagina(3))
    # Una para ubicar al dueno y otra para la pagina, sin importar cuantas filas.
    assert len(consultas) == 2
    primera = ana.get(limite=3).json()
    assert len(primera["datos"]) == 3 and primera["pagina"]["tiene_mas"]
    segunda = ana.get(limite=3, cursor=primera["pagina"]["siguiente_cursor"]).json()
    nombres = [c["nombre"] for c in primera["datos"] + segunda["datos"]]
    assert nombres == [f"Cliente {i}" for i in range(4, -1, -1)]
    assert [c["nombre"] for c in ana.get(etiqueta="vip").json()["datos"]] == [
        "Cliente 3",
        "Cliente 1",
    ]
    assert [c["nombre"] for c in ana.get(texto="1111112").json()["datos"]] == ["Cliente 2"]


def test_un_cursor_manipulado_responde_422(ana: Sesion) -> None:
    assert ana.get(cursor="abc").status_code == 422


def test_etiquetas_sin_repetir_y_solo_propias(ana: Sesion, luis: Sesion) -> None:
    ana.crear("0991111111", etiquetas="vip, cliente")
    ana.crear("0992222222", etiquetas="vip")
    luis.crear("0993333333", etiquetas="secreta")
    assert ana.get("/etiquetas").json() == {"datos": ["cliente", "vip"]}


def test_un_contacto_del_sistema_actual_aparece_en_la_v1(ana: Sesion) -> None:
    Contact.objects.create(owner=ana.usuario, phone_number="593991112222", tags="vip, lead")
    (contacto,) = ana.get().json()["datos"]
    assert id_publico(contacto["id"])
    assert contacto["etiquetas"] == ["vip", "lead"]
    assert contacto["nombre"] == "593991112222"


def test_importar_con_encabezado_informa_las_rechazadas(ana: Sesion) -> None:
    csv = (
        "telefono,nombre,etiquetas,notas\n"
        "0991112222,Pedro,vip,cliente fiel\n"
        "022345678,Fijo,,\n"
        "\n"
        '0992223333,Maria,"vip,lead",\n'
        "0991112222,Pedro Perez,,\n"
    )
    respuesta = ana.importar(csv)
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert (cuerpo["creados"], cuerpo["actualizados"], cuerpo["total_rechazadas"]) == (2, 1, 1)
    assert cuerpo["rechazadas"][0]["fila"] == 3
    assert cuerpo["rechazadas"][0]["campo"] == "telefono"
    pedro = Contact.objects.get(phone_number="593991112222")
    assert pedro.full_name == "Pedro Perez"
    assert pedro.custom_data == {"notas": "cliente fiel"}


def test_importar_sin_encabezado_y_otro_separador(ana: Sesion) -> None:
    respuesta = ana.importar("0991112222;Pedro;vip\n", separador=";", encabezado="false")
    assert respuesta.json()["creados"] == 1
    assert Contact.objects.get().full_name == "Pedro"


@pytest.mark.parametrize(
    ("contenido", "nombre", "campos"),
    [
        ("nombre,etiquetas\nPedro,vip\n", "c.csv", {}),
        ("", "c.csv", {}),
        ("telefono\n0991112222\n", "c.xlsx", {}),
        ("telefono\n0991112222\n", "c.csv", {"separador": "#"}),
    ],
)
def test_importar_un_archivo_invalido_responde_422(
    ana: Sesion, contenido: str, nombre: str, campos: dict[str, str]
) -> None:
    respuesta = ana.importar(contenido, nombre, **campos)
    assert respuesta.status_code == 422
    cuerpo = respuesta.json()
    campo = cuerpo.get("campo") or cuerpo["errores"][0]["campo"]
    assert campo in {"archivo", "separador"}
    assert not Contact.objects.exists()


def test_importar_respeta_el_aislamiento(ana: Sesion, luis: Sesion) -> None:
    luis.crear("0991112222", nombre="De Luis")
    ana.importar("telefono,nombre\n0991112222,De Ana\n")
    assert Contact.objects.get(owner=luis.usuario).full_name == "De Luis"
    assert Contact.objects.get(owner=ana.usuario).full_name == "De Ana"


def test_importar_10000_filas_por_lotes(ana: Sesion) -> None:
    filas = "\n".join(f"5939{i:08d},Cliente {i},masivo" for i in range(10_000))
    with CaptureQueriesContext(connection) as consultas:
        respuesta = ana.importar("telefono,nombre,etiquetas\n" + filas + "\n")
    assert respuesta.json()["creados"] == 10_000
    assert ContactoFila.objects.filter(usuario=ana.usuario).count() == 10_000
    # 20 lotes de 500: unas pocas consultas por lote, nunca una por fila.
    assert len(consultas) < 200
    repetida = ana.importar("telefono,nombre,etiquetas\n" + filas + "\n").json()
    assert (repetida["creados"], repetida["actualizados"]) == (0, 10_000)
