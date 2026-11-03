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
from masssend.infrastructure.adapters.pagos.heredadas import monto_paypal
from masssend.infrastructure.adapters.pagos.payphone import id_cliente, monto
from masssend.infrastructure.composition.creditos import pasarelas_reales
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
    settings.PAYPAL_CLIENT_ID = "cliente"
    settings.PAYPAL_CLIENT_SECRET = "secreto-de-prueba"


@pytest.mark.parametrize("falta", ["PAYPAL_CLIENT_ID", "PAYPAL_CLIENT_SECRET"])
def test_paypal_sin_credenciales_responde_503_sin_crear_compra(
    client: Client, settings: Any, falta: str
) -> None:
    paypal_real(settings)
    setattr(settings, falta, "")
    _, cabecera = cuenta()
    with patch(RUTA) as llamada:
        respuesta = post(
            client, "checkout", {"paquete_id": paquete().id, "pasarela": "paypal"}, cabecera
        )
    assert respuesta.status_code == 503
    assert respuesta.json()["codigo"] == "servicio_no_disponible"
    llamada.assert_not_called()
    assert not PaymentTransaction.objects.exists()


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


@pytest.mark.parametrize(
    ("fake", "paypal", "payphone", "reales"),
    [
        (True, "auto", "auto", set()),
        (False, "auto", "auto", {"PAYPAL", "PAYPHONE"}),
        (True, "real", "auto", {"PAYPAL"}),
        (True, "auto", "real", {"PAYPHONE"}),
        (False, "falsa", "auto", {"PAYPHONE"}),
        (False, "real", "falsa", {"PAYPAL"}),
    ],
)
def test_cada_pasarela_se_activa_por_separado(
    settings: Any, fake: bool, paypal: str, payphone: str, reales: set[str]
) -> None:
    settings.PASARELA_PAGO_FAKE = fake
    settings.PASARELA_PAYPAL = paypal
    settings.PASARELA_PAYPHONE = payphone
    assert pasarelas_reales() == reales


RUTA_PAYPHONE = "masssend.infrastructure.adapters.pagos.payphone.requests.post"
PREPARADO = {
    "paymentId": "pago-1",
    "payWithCard": "https://pay.payphonetodoesposible.com/Anonymous/Pay?id=1",
    "payWithPayPhone": "https://payp.page.link/abc",
}


def payphone_real(settings: Any) -> None:
    settings.PASARELA_PAYPHONE = "real"
    settings.PAYPHONE_TOKEN = "token-de-prueba"
    settings.PAYPHONE_STORE_ID = "tienda-1"
    settings.PAYPHONE_BASE_URL = "https://payphone.prueba/"
    settings.PAYPHONE_RETORNO_V1 = "http://localhost:5173/billing/return?provider=payphone"


def iniciar_payphone(client: Client, cabecera: dict[str, str]) -> tuple[dict[str, Any], Any]:
    with patch(RUTA_PAYPHONE, return_value=respuesta_http(PREPARADO)) as llamada:
        respuesta = post(
            client, "checkout", {"paquete_id": paquete().id, "pasarela": "payphone"}, cabecera
        )
    assert respuesta.status_code == 201, respuesta.content
    return respuesta.json(), llamada


def confirmacion_payphone(
    referencia: str, estado: int = 3, monto_centavos: int = 450
) -> dict[str, Any]:
    return {
        "statusCode": estado,
        "transactionStatus": "Approved" if estado == 3 else "Canceled",
        "clientTransactionId": referencia,
        "amount": monto_centavos,
        "currency": "USD",
        "transactionId": 123,
        "email": "cliente@correo.ec",
        "lastDigits": "4242",
    }


def confirmar_payphone(
    client: Client, cabecera: dict[str, str], compra_id: str, cuerpo: Any, estado_http: int = 200
) -> tuple[Any, Any]:
    with patch(RUTA_PAYPHONE, return_value=respuesta_http(cuerpo, estado_http)) as llamada:
        respuesta = post(
            client,
            "confirmar",
            {"compra_id": compra_id, "datos_pasarela": {"id": "123"}},
            cabecera,
        )
    return respuesta, llamada


def test_payphone_prepara_el_boton_con_el_precio_del_paquete(
    client: Client, settings: Any
) -> None:
    payphone_real(settings)
    _, cabecera = cuenta()
    compra, llamada = iniciar_payphone(client, cabecera)
    assert compra["url_pago"] == PREPARADO["payWithCard"]
    assert compra["pasarela"] == "PAYPHONE"
    url = llamada.call_args.args[0]
    cuerpo = llamada.call_args.kwargs["json"]
    assert url == "https://payphone.prueba/api/button/Prepare"
    assert llamada.call_args.kwargs["headers"]["Authorization"] == "Bearer token-de-prueba"
    assert cuerpo["amount"] == cuerpo["amountWithoutTax"] == 450
    assert cuerpo["storeId"] == "tienda-1"
    assert cuerpo["responseUrl"] == settings.PAYPHONE_RETORNO_V1
    assert cuerpo["clientTransactionId"] == id_cliente(compra["compra_id"])
    assert len(cuerpo["clientTransactionId"]) <= 15
    assert PaymentTransaction.objects.get().provider_reference == cuerpo["clientTransactionId"]


def test_payphone_aprobado_acredita_una_vez(client: Client, settings: Any) -> None:
    payphone_real(settings)
    usuario, cabecera = cuenta()
    compra, _ = iniciar_payphone(client, cabecera)
    referencia = id_cliente(compra["compra_id"])
    respuesta, llamada = confirmar_payphone(
        client, cabecera, compra["compra_id"], confirmacion_payphone(referencia)
    )
    assert respuesta.json() == {"estado": "aprobada", "creditos": 100, "ya_procesada": False}
    assert llamada.call_args.args[0] == "https://payphone.prueba/api/button/V2/Confirm"
    assert llamada.call_args.kwargs["json"] == {"id": 123, "clientTxId": referencia}
    assert saldo(usuario) == 100
    otra, otra_llamada = confirmar_payphone(
        client, cabecera, compra["compra_id"], confirmacion_payphone(referencia)
    )
    assert otra.json()["ya_procesada"] is True
    otra_llamada.assert_not_called()
    assert saldo(usuario) == 100


def test_payphone_no_guarda_correo_ni_tarjeta(client: Client, settings: Any) -> None:
    payphone_real(settings)
    _, cabecera = cuenta()
    compra, _ = iniciar_payphone(client, cabecera)
    referencia = id_cliente(compra["compra_id"])
    confirmar_payphone(client, cabecera, compra["compra_id"], confirmacion_payphone(referencia))
    guardado = PaymentTransaction.objects.get().raw_response
    assert guardado["statusCode"] == 3
    assert "email" not in guardado
    assert "lastDigits" not in guardado


@pytest.mark.parametrize(
    "cambio",
    [
        {"statusCode": 2},
        {"clientTransactionId": "MSOTRACOMPRA01"},
        {"amount": 1},
    ],
    ids=["cancelado", "id-de-otra-compra", "otro-monto"],
)
def test_payphone_no_acredita_si_el_cobro_no_coincide(
    client: Client, settings: Any, cambio: dict[str, Any]
) -> None:
    payphone_real(settings)
    usuario, cabecera = cuenta()
    compra, _ = iniciar_payphone(client, cabecera)
    cuerpo = {**confirmacion_payphone(id_cliente(compra["compra_id"])), **cambio}
    respuesta, _ = confirmar_payphone(client, cabecera, compra["compra_id"], cuerpo)
    assert respuesta.json()["estado"] == "rechazada"
    assert saldo(usuario) == 0


@pytest.mark.parametrize("datos", [{}, {"id": ""}, {"id": "abc"}, {"id": 0}, {"id": True}])
def test_payphone_exige_el_id_del_retorno(
    client: Client, settings: Any, datos: dict[str, Any]
) -> None:
    payphone_real(settings)
    _, cabecera = cuenta()
    compra, _ = iniciar_payphone(client, cabecera)
    with patch(RUTA_PAYPHONE) as llamada:
        respuesta = post(
            client,
            "confirmar",
            {"compra_id": compra["compra_id"], "datos_pasarela": datos},
            cabecera,
        )
    assert respuesta.status_code == 422
    assert respuesta.json()["campo"] == "datos_pasarela"
    llamada.assert_not_called()
    assert PaymentTransaction.objects.get().status == PaymentTransaction.STATUS_PENDING


def test_payphone_transaccion_inexistente_deja_la_compra_pendiente(
    client: Client, settings: Any
) -> None:
    payphone_real(settings)
    _, cabecera = cuenta()
    compra, _ = iniciar_payphone(client, cabecera)
    respuesta, _ = confirmar_payphone(
        client,
        cabecera,
        compra["compra_id"],
        {"message": "Transacción no encontrada", "errorCode": 20},
        estado_http=400,
    )
    assert respuesta.status_code == 422
    assert "no encontrada" in respuesta.json()["detail"]
    assert PaymentTransaction.objects.get().status == PaymentTransaction.STATUS_PENDING


@pytest.mark.parametrize(
    "fallo",
    [
        {"side_effect": requests.ConnectionError},
        {"return_value": respuesta_http({"message": "token"}, 401)},
        {"return_value": respuesta_http({}, 500)},
        {"return_value": respuesta_http("texto plano")},
    ],
    ids=["sin-red", "token-invalido", "error-interno", "sin-json"],
)
def test_si_payphone_falla_al_preparar_responde_503_sin_compra(
    client: Client, settings: Any, fallo: dict[str, Any]
) -> None:
    payphone_real(settings)
    _, cabecera = cuenta()
    with patch(RUTA_PAYPHONE, **fallo):
        respuesta = post(
            client, "checkout", {"paquete_id": paquete().id, "pasarela": "payphone"}, cabecera
        )
    assert respuesta.status_code == 503
    assert not PaymentTransaction.objects.exists()


def test_payphone_sin_url_de_pago_responde_503(client: Client, settings: Any) -> None:
    payphone_real(settings)
    _, cabecera = cuenta()
    with patch(RUTA_PAYPHONE, return_value=respuesta_http({"paymentId": "x"})):
        respuesta = post(
            client, "checkout", {"paquete_id": paquete().id, "pasarela": "payphone"}, cabecera
        )
    assert respuesta.status_code == 503


@pytest.mark.parametrize("falta", ["PAYPHONE_TOKEN", "PAYPHONE_STORE_ID"])
def test_payphone_sin_credenciales_responde_503_sin_llamar(
    client: Client, settings: Any, falta: str
) -> None:
    payphone_real(settings)
    setattr(settings, falta, "")
    _, cabecera = cuenta()
    with patch(RUTA_PAYPHONE) as llamada:
        respuesta = post(
            client, "checkout", {"paquete_id": paquete().id, "pasarela": "payphone"}, cabecera
        )
    assert respuesta.status_code == 503
    assert respuesta.json()["detail"] == "PayPhone no está configurado."
    llamada.assert_not_called()


def test_payphone_real_no_vuelve_real_a_paypal(client: Client, settings: Any) -> None:
    payphone_real(settings)
    _, cabecera = cuenta()
    compra = iniciar(client, cabecera)
    assert compra["url_pago"].startswith("https://pasarela.falsa/")


def test_lee_los_montos_de_cada_pasarela() -> None:
    assert monto_paypal(captura("4.50")) == Dinero(450)
    assert monto_paypal({}) is None
    assert monto({"amount": 450}) == Dinero(450)
    assert monto({"amount": "abc"}) is None
    assert monto({}) is None
