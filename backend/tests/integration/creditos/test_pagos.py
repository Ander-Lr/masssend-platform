"""Pagos contra PostgreSQL, con la pasarela falsa y las pasarelas actuales simuladas."""

import json
import threading
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import Client
from rest_framework_simplejwt.tokens import AccessToken

from billing.models import CreditPack, CreditWallet, PaymentTransaction
from masssend.domain.shared.dinero import Dinero
from masssend.infrastructure.adapters.pagos.heredadas import monto_paypal, monto_payphone
from masssend.infrastructure.composition.root import contenedor
from masssend.infrastructure.persistence.identidad.models import CuentaIdentidad

pytestmark = pytest.mark.django_db
Usuario = get_user_model()


@pytest.fixture(autouse=True)
def pasarela_falsa(settings: Any) -> None:
    settings.PASARELA_PAGO_FAKE = True


def cuenta(nombre: str = "ana", saldo: int = 0) -> tuple[Any, dict[str, str]]:
    usuario = Usuario.objects.create_user(f"{nombre}@prueba.local")
    public_id = contenedor.generador_ids().nuevo()
    CuentaIdentidad.objects.create(usuario=usuario, public_id=public_id)
    CreditWallet.objects.create(user=usuario, balance=saldo)
    token = AccessToken.for_user(usuario)
    token["public_id"] = str(public_id)
    return usuario, {"HTTP_AUTHORIZATION": f"Bearer {token}"}


def paquete() -> CreditPack:
    return CreditPack.objects.create(name="Base", credits=100, price_usd=Decimal("4.50"))


def post(cliente: Client, ruta: str, datos: dict[str, Any], cabecera: dict[str, str]) -> Any:
    return cliente.post(
        f"/api/v1/pagos/{ruta}", json.dumps(datos), content_type="application/json", **cabecera
    )


def iniciar(client: Client, cabecera: dict[str, str], **extra: Any) -> dict[str, Any]:
    respuesta = post(
        client,
        "checkout",
        {"paquete_id": paquete().id, "pasarela": "paypal", **extra},
        cabecera,
    )
    assert respuesta.status_code == 201, respuesta.content
    cuerpo: dict[str, Any] = respuesta.json()
    return cuerpo


def saldo(usuario: Any) -> int:
    return CreditWallet.objects.get(user=usuario).balance


def test_checkout_crea_una_compra_pendiente_con_id_publico(client: Client) -> None:
    usuario, cabecera = cuenta()
    compra = iniciar(client, cabecera)
    assert compra["compra_id"][14] == "7"
    assert (compra["monto"], compra["moneda"], compra["creditos"]) == ("4.50", "USD", 100)
    fila = PaymentTransaction.objects.get(pk=compra["compra_id"])
    assert fila.user == usuario
    assert fila.status == PaymentTransaction.STATUS_PENDING


def test_cambiar_el_monto_en_la_peticion_no_altera_lo_cobrado(client: Client) -> None:
    usuario, cabecera = cuenta()
    compra = iniciar(client, cabecera, monto="0.01", amount_usd="0.01", creditos=999999)
    assert (compra["monto"], compra["creditos"]) == ("4.50", 100)
    post(client, "confirmar", {"compra_id": compra["compra_id"]}, cabecera)
    assert saldo(usuario) == 100
    assert PaymentTransaction.objects.get().amount_usd == Decimal("4.50")


def test_un_cobro_por_otro_monto_no_acredita(client: Client) -> None:
    usuario, cabecera = cuenta()
    compra = iniciar(client, cabecera)
    respuesta = post(
        client,
        "confirmar",
        {"compra_id": compra["compra_id"], "datos_pasarela": {"monto_cobrado": "0.01"}},
        cabecera,
    )
    assert respuesta.json()["estado"] == "rechazada"
    assert saldo(usuario) == 0


def test_diez_confirmaciones_iguales_acreditan_una_vez(client: Client) -> None:
    usuario, cabecera = cuenta()
    compra = iniciar(client, cabecera)
    respuestas = [
        post(client, "confirmar", {"compra_id": compra["compra_id"]}, cabecera).json()
        for _ in range(10)
    ]
    assert saldo(usuario) == 100
    assert [r["ya_procesada"] for r in respuestas] == [False] + [True] * 9


@pytest.mark.django_db(transaction=True)
def test_diez_confirmaciones_simultaneas_acreditan_una_vez() -> None:
    usuario, cabecera = cuenta()
    compra = iniciar(Client(), cabecera)
    barrera = threading.Barrier(10)
    estados: list[int] = []

    def confirmar() -> None:
        try:
            barrera.wait()
            respuesta = post(Client(), "confirmar", {"compra_id": compra["compra_id"]}, cabecera)
            estados.append(respuesta.status_code)
        finally:
            connection.close()

    hilos = [threading.Thread(target=confirmar) for _ in range(10)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join()
    assert estados == [200] * 10
    assert saldo(usuario) == 100


def test_un_pago_rechazado_no_acredita_y_puede_reintentarse(client: Client) -> None:
    usuario, cabecera = cuenta()
    compra = iniciar(client, cabecera)
    rechazo = post(
        client,
        "confirmar",
        {"compra_id": compra["compra_id"], "datos_pasarela": {"resultado": "rechazado"}},
        cabecera,
    )
    assert rechazo.json() == {"estado": "rechazada", "creditos": 0, "ya_procesada": False}
    assert saldo(usuario) == 0
    post(client, "confirmar", {"compra_id": compra["compra_id"]}, cabecera)
    assert saldo(usuario) == 100


def test_una_compra_ajena_responde_404_y_no_acredita(client: Client) -> None:
    dueno, cabecera = cuenta()
    otro, cabecera_otro = cuenta("luis")
    compra = iniciar(client, cabecera)
    respuesta = post(client, "confirmar", {"compra_id": compra["compra_id"]}, cabecera_otro)
    assert respuesta.status_code == 404
    assert (saldo(dueno), saldo(otro)) == (0, 0)


def test_la_compra_aparece_en_movimientos(client: Client) -> None:
    _, cabecera = cuenta()
    compra = iniciar(client, cabecera)
    post(client, "confirmar", {"compra_id": compra["compra_id"]}, cabecera)
    datos = client.get("/api/v1/creditos/movimientos", **cabecera).json()["datos"]
    assert [(m["tipo"], m["creditos"], m["detalle"]) for m in datos] == [
        ("compra", 100, "PAYPAL")
    ]


@pytest.mark.parametrize(
    ("datos", "estado"),
    [
        ({"paquete_id": 99999, "pasarela": "paypal"}, 404),
        ({"paquete_id": "x", "pasarela": "paypal"}, 422),
        ({"pasarela": "paypal"}, 422),
    ],
)
def test_checkout_valida(client: Client, datos: dict[str, Any], estado: int) -> None:
    _, cabecera = cuenta()
    assert post(client, "checkout", datos, cabecera).status_code == estado


def test_una_pasarela_desconocida_responde_422(client: Client) -> None:
    _, cabecera = cuenta()
    respuesta = post(
        client, "checkout", {"paquete_id": paquete().id, "pasarela": "bitcoin"}, cabecera
    )
    assert respuesta.status_code == 422
    assert respuesta.json()["campo"] == "pasarela"


def test_un_paquete_inactivo_no_se_compra(client: Client) -> None:
    _, cabecera = cuenta()
    inactivo = CreditPack.objects.create(name="X", credits=1, price_usd=1, is_active=False)
    datos = {"paquete_id": inactivo.id, "pasarela": "paypal"}
    respuesta = post(client, "checkout", datos, cabecera)
    assert respuesta.status_code == 404


@pytest.mark.parametrize("compra_id", ["no-uuid", "9f1c0a52-3c3e-4b0e-8a57-2f1f4a3d1b11"])
def test_confirmar_exige_uuid7(client: Client, compra_id: str) -> None:
    _, cabecera = cuenta()
    assert post(client, "confirmar", {"compra_id": compra_id}, cabecera).status_code == 422


def test_pagos_exigen_token(client: Client) -> None:
    assert post(client, "checkout", {}, {}).status_code == 401
    assert post(client, "confirmar", {}, {}).status_code == 401


def respuesta_http(cuerpo: dict[str, Any], estado: int = 200) -> MagicMock:
    simulada = MagicMock(status_code=estado)
    simulada.json.return_value = cuerpo
    return simulada


def paypal_real(settings: Any) -> None:
    settings.PASARELA_PAGO_FAKE = False
    settings.PAYPAL_BASE_URL = "https://paypal.prueba"


RUTA = "billing.services.gateways.paypal_gateway.requests.post"
TOKEN = {"access_token": "t"}
ORDEN = {"id": "ORDEN1", "links": [{"rel": "approve", "href": "https://paypal.prueba/ok"}]}


def captura(valor: str) -> dict[str, Any]:
    return {
        "status": "COMPLETED",
        "purchase_units": [
            {"payments": {"captures": [{"amount": {"value": valor, "currency_code": "USD"}}]}}
        ],
    }


def test_paypal_con_el_monto_correcto_acredita(client: Client, settings: Any) -> None:
    paypal_real(settings)
    usuario, cabecera = cuenta()
    with patch(RUTA, side_effect=[respuesta_http(TOKEN), respuesta_http(ORDEN)]):
        compra = iniciar(client, cabecera)
    assert compra["url_pago"] == "https://paypal.prueba/ok"
    with patch(RUTA, side_effect=[respuesta_http(TOKEN), respuesta_http(captura("4.50"))]):
        respuesta = post(client, "confirmar", {"compra_id": compra["compra_id"]}, cabecera)
    assert respuesta.json()["estado"] == "aprobada"
    assert saldo(usuario) == 100


def test_paypal_con_otro_monto_no_acredita(client: Client, settings: Any) -> None:
    paypal_real(settings)
    usuario, cabecera = cuenta()
    with patch(RUTA, side_effect=[respuesta_http(TOKEN), respuesta_http(ORDEN)]):
        compra = iniciar(client, cabecera)
    with patch(RUTA, side_effect=[respuesta_http(TOKEN), respuesta_http(captura("0.01"))]):
        respuesta = post(client, "confirmar", {"compra_id": compra["compra_id"]}, cabecera)
    assert respuesta.json()["estado"] == "rechazada"
    assert saldo(usuario) == 0


def test_si_paypal_cae_responde_503_y_la_compra_sigue_pendiente(
    client: Client, settings: Any
) -> None:
    paypal_real(settings)
    _, cabecera = cuenta()
    with patch(RUTA, side_effect=[respuesta_http(TOKEN), respuesta_http(ORDEN)]):
        compra = iniciar(client, cabecera)
    with patch(RUTA, side_effect=requests.ConnectionError):
        respuesta = post(client, "confirmar", {"compra_id": compra["compra_id"]}, cabecera)
    assert respuesta.status_code == 503
    assert PaymentTransaction.objects.get().status == PaymentTransaction.STATUS_PENDING


def test_payphone_exige_su_id_al_confirmar(client: Client, settings: Any) -> None:
    settings.PASARELA_PAGO_FAKE = False
    _, cabecera = cuenta()
    ruta = "billing.services.gateways.payphone_gateway.requests.post"
    simulada = respuesta_http({"payWithPayPhone": "https://payphone.prueba"})
    with patch(ruta, return_value=simulada):
        respuesta = post(
            client, "checkout", {"paquete_id": paquete().id, "pasarela": "payphone"}, cabecera
        )
    compra = respuesta.json()
    assert compra["url_pago"] == "https://payphone.prueba"
    confirmacion = post(client, "confirmar", {"compra_id": compra["compra_id"]}, cabecera)
    assert confirmacion.status_code == 422
    assert confirmacion.json()["campo"] == "datos_pasarela"


def test_lee_los_montos_de_cada_pasarela() -> None:
    assert monto_paypal(captura("4.50")) == Dinero(450)
    assert monto_paypal({}) is None
    assert monto_payphone({"amount": 450}) == Dinero(450)
    assert monto_payphone({}) is None
