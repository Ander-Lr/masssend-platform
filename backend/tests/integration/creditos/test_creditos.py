"""Creditos contra PostgreSQL: API, contrato real de reservas y concurrencia."""

import threading
from collections.abc import Callable
from decimal import Decimal
from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework_simplejwt.tokens import AccessToken

from billing.models import CreditPack, CreditSpend, CreditWallet, PaymentTransaction
from billing.repositories import wallet_repository
from billing.services import wallet_service
from masssend.application.envio.puertos import (
    IReservaCreditos,
    ReservaCreada,
    ReservaRechazada,
)
from masssend.domain.shared.errores import (
    DatosInvalidos,
    EstadoInvalido,
    RecursoNoEncontrado,
    SaldoInsuficiente,
)
from masssend.domain.shared.identificadores import IdPublico
from masssend.infrastructure.composition.creditos import contenedor_creditos
from masssend.infrastructure.composition.root import contenedor
from masssend.infrastructure.persistence.creditos.models import ConsumoCredito, ReservaCreditos
from masssend.infrastructure.persistence.identidad.models import CuentaIdentidad

pytestmark = pytest.mark.django_db
Usuario = get_user_model()


def nuevo_id() -> IdPublico:
    return contenedor.generador_ids().nuevo()


def cuenta(nombre: str = "ana", saldo: int = 10) -> tuple[Any, IdPublico]:
    usuario = Usuario.objects.create_user(f"{nombre}@prueba.local", password="clave-larga-123")
    public_id = nuevo_id()
    CuentaIdentidad.objects.create(usuario=usuario, public_id=public_id)
    CreditWallet.objects.create(user=usuario, balance=saldo)
    return usuario, public_id


def bearer(usuario: Any, public_id: IdPublico) -> dict[str, str]:
    token = AccessToken.for_user(usuario)
    token["public_id"] = str(public_id)
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


def puerto() -> IReservaCreditos:
    return contenedor_creditos.reserva_creditos()


def saldo_real(usuario: Any) -> int:
    return CreditWallet.objects.get(user=usuario).balance


def reservar(dueno: IdPublico, cantidad: int) -> ReservaCreada:
    resultado = puerto().reservar(dueno, nuevo_id(), cantidad)
    assert isinstance(resultado, ReservaCreada)
    return resultado


def test_reservar_aparta_sin_descontar_y_el_saldo_lo_refleja(client: Client) -> None:
    usuario, dueno = cuenta()
    reservar(dueno, 4)
    assert saldo_real(usuario) == 10
    respuesta = client.get("/api/v1/creditos/saldo", **bearer(usuario, dueno))
    assert respuesta.json() == {"saldo": 10, "reservado": 4, "disponible": 6}


def test_el_id_de_reserva_es_uuid7() -> None:
    _, dueno = cuenta()
    assert reservar(dueno, 1).reserva_id.version == 7


def test_sin_saldo_devuelve_rechazo_y_no_crea_nada() -> None:
    _, dueno = cuenta(saldo=2)
    assert puerto().reservar(dueno, nuevo_id(), 3) == ReservaRechazada(requerido=3, disponible=2)
    assert not ReservaCreditos.objects.exists()


def test_lo_reservado_no_se_vuelve_a_reservar() -> None:
    _, dueno = cuenta(saldo=5)
    reservar(dueno, 4)
    assert puerto().reservar(dueno, nuevo_id(), 2) == ReservaRechazada(requerido=2, disponible=1)


@pytest.mark.parametrize("cantidad", [0, -1])
def test_rechaza_cantidades_no_positivas(cantidad: int) -> None:
    _, dueno = cuenta()
    with pytest.raises(DatosInvalidos):
        puerto().reservar(dueno, nuevo_id(), cantidad)


def test_consumir_descuenta_y_deja_constancia() -> None:
    usuario, dueno = cuenta()
    reserva = reservar(dueno, 2)
    assert puerto().consumir(reserva.reserva_id, nuevo_id()).restante == 1
    assert saldo_real(usuario) == 9
    assert CreditSpend.objects.get(user=usuario).amount == 1


def test_el_mismo_mensaje_no_se_cobra_dos_veces() -> None:
    usuario, dueno = cuenta()
    reserva = reservar(dueno, 2)
    mensaje = nuevo_id()
    puerto().consumir(reserva.reserva_id, mensaje)
    assert puerto().consumir(reserva.reserva_id, mensaje).duplicado
    assert saldo_real(usuario) == 9
    assert CreditSpend.objects.count() == 1


def test_no_se_consume_mas_de_lo_reservado() -> None:
    usuario, dueno = cuenta()
    reserva = reservar(dueno, 1)
    puerto().consumir(reserva.reserva_id, nuevo_id())
    with pytest.raises(EstadoInvalido):
        puerto().consumir(reserva.reserva_id, nuevo_id())
    assert saldo_real(usuario) == 9


def test_liberar_devuelve_lo_pendiente_una_sola_vez(client: Client) -> None:
    usuario, dueno = cuenta()
    reserva = reservar(dueno, 3)
    puerto().consumir(reserva.reserva_id, nuevo_id())
    assert puerto().liberar(reserva.reserva_id).liberados == 2
    assert puerto().liberar(reserva.reserva_id).liberados == 0
    respuesta = client.get("/api/v1/creditos/saldo", **bearer(usuario, dueno))
    assert respuesta.json() == {"saldo": 9, "reservado": 0, "disponible": 9}


def test_una_reserva_inexistente_no_se_encuentra() -> None:
    with pytest.raises(RecursoNoEncontrado):
        puerto().liberar(nuevo_id())


def test_si_el_sistema_actual_agoto_el_saldo_no_queda_negativo() -> None:
    usuario, dueno = cuenta(saldo=1)
    reserva = reservar(dueno, 1)
    wallet_service.spend_credits(usuario, 1)
    with pytest.raises(SaldoInsuficiente):
        puerto().consumir(reserva.reserva_id, nuevo_id())
    assert saldo_real(usuario) == 0
    assert ReservaCreditos.objects.get().restante == 1
    assert not ConsumoCredito.objects.exists()


def test_una_acreditacion_del_sistema_actual_se_ve_en_la_v1(client: Client) -> None:
    usuario, dueno = cuenta(saldo=1)
    wallet_repository.add_credits(usuario, 5)
    assert client.get("/api/v1/creditos/saldo", **bearer(usuario, dueno)).json()["saldo"] == 6


def test_la_primera_consulta_entrega_los_creditos_de_bienvenida(
    client: Client, settings: Any
) -> None:
    settings.FREE_SIGNUP_CREDITS = 7
    usuario = Usuario.objects.create_user("nuevo@prueba.local")
    public_id = nuevo_id()
    CuentaIdentidad.objects.create(usuario=usuario, public_id=public_id)
    respuesta = client.get("/api/v1/creditos/saldo", **bearer(usuario, public_id))
    assert respuesta.json()["saldo"] == 7


def en_paralelo(acciones: list[Callable[[], Any]]) -> list[Any]:
    barrera = threading.Barrier(len(acciones))
    resultados: list[Any] = []

    def correr(accion: Callable[[], Any]) -> None:
        try:
            barrera.wait()
            resultados.append(accion())
        except Exception as error:  # noqa: BLE001
            resultados.append(error)
        finally:
            connection.close()

    hilos = [threading.Thread(target=correr, args=(a,)) for a in acciones]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join()
    return resultados


@pytest.mark.django_db(transaction=True)
def test_dos_lanzamientos_con_saldo_para_uno_solo_reservan_una_vez() -> None:
    _, dueno = cuenta(saldo=1)
    resultados = en_paralelo([lambda: puerto().reservar(dueno, nuevo_id(), 1)] * 2)
    assert sorted(type(r).__name__ for r in resultados) == ["ReservaCreada", "ReservaRechazada"]


@pytest.mark.django_db(transaction=True)
def test_diez_lanzamientos_nunca_superan_el_saldo() -> None:
    _, dueno = cuenta(saldo=3)
    resultados = en_paralelo([lambda: puerto().reservar(dueno, nuevo_id(), 1)] * 10)
    assert sum(isinstance(r, ReservaCreada) for r in resultados) == 3


@pytest.mark.django_db(transaction=True)
def test_el_mismo_mensaje_en_paralelo_cobra_una_vez() -> None:
    usuario, dueno = cuenta()
    reserva = reservar(dueno, 2)
    mensaje = nuevo_id()
    resultados = en_paralelo([lambda: puerto().consumir(reserva.reserva_id, mensaje)] * 5)
    assert sum(not r.duplicado for r in resultados) == 1
    assert saldo_real(usuario) == 9


@pytest.mark.django_db(transaction=True)
def test_consumir_y_liberar_en_paralelo_cuadran_el_saldo() -> None:
    usuario, dueno = cuenta()
    reserva = reservar(dueno, 5)
    acciones = [
        *[lambda: puerto().consumir(reserva.reserva_id, nuevo_id()) for _ in range(5)],
        lambda: puerto().liberar(reserva.reserva_id),
    ]
    en_paralelo(acciones)
    consumidos = ConsumoCredito.objects.count()
    assert saldo_real(usuario) == 10 - consumidos
    assert ReservaCreditos.objects.get().restante == 0


def test_paquetes_solo_activos_y_con_precio_exacto(client: Client) -> None:
    usuario, dueno = cuenta()
    CreditPack.objects.all().delete()
    CreditPack.objects.create(name="Base", credits=100, price_usd=Decimal("4.50"))
    CreditPack.objects.create(name="Oculto", credits=1, price_usd=1, is_active=False)
    respuesta = client.get("/api/v1/creditos/paquetes", **bearer(usuario, dueno))
    assert respuesta.json()["datos"] == [
        {
            "id": CreditPack.objects.get(name="Base").id,
            "nombre": "Base",
            "creditos": 100,
            "precio": "4.50",
            "moneda": "USD",
        }
    ]


@pytest.mark.parametrize("ruta", ["paquetes", "saldo", "movimientos"])
def test_sin_token_responde_401(client: Client, ruta: str) -> None:
    respuesta = client.get(f"/api/v1/creditos/{ruta}")
    assert respuesta.status_code == 401
    assert respuesta["Content-Type"] == "application/problem+json"


def compra(usuario: Any, estado: str = PaymentTransaction.STATUS_APPROVED) -> None:
    PaymentTransaction.objects.create(
        user=usuario,
        provider=PaymentTransaction.PROVIDER_PAYPAL,
        provider_reference="r",
        amount_usd=1,
        credits=50,
        status=estado,
    )


def test_movimientos_mezcla_compras_y_consumos_sin_datos_ajenos(client: Client) -> None:
    usuario, dueno = cuenta()
    otro, _ = cuenta("luis")
    compra(usuario)
    compra(usuario, PaymentTransaction.STATUS_PENDING)
    compra(otro)
    CreditSpend.objects.create(user=usuario, amount=1, reason="Campaña")
    CreditSpend.objects.create(user=otro, amount=1, reason="Ajena")
    datos = client.get("/api/v1/creditos/movimientos", **bearer(usuario, dueno)).json()["datos"]
    assert sorted((m["tipo"], m["creditos"]) for m in datos) == [("compra", 50), ("consumo", 1)]


def test_movimientos_recorre_todo_sin_repetir_ni_perder_filas(client: Client) -> None:
    usuario, dueno = cuenta()
    for _ in range(4):
        compra(usuario)
    CreditSpend.objects.bulk_create(
        [CreditSpend(user=usuario, amount=1, reason=str(n)) for n in range(5)]
    )
    cabecera = bearer(usuario, dueno)
    vistos: list[dict[str, Any]] = []
    cursor = None
    for _ in range(10):
        parametros = {"limite": 2, **({"cursor": cursor} if cursor else {})}
        pagina = client.get("/api/v1/creditos/movimientos", parametros, **cabecera).json()
        vistos.extend(pagina["datos"])
        cursor = pagina["pagina"]["siguiente_cursor"]
        if cursor is None:
            break
    assert len(vistos) == 9
    assert sum(m["tipo"] == "compra" for m in vistos) == 4
    assert sorted(m["detalle"] for m in vistos if m["tipo"] == "consumo") == list("01234")
    fechas = [m["fecha"] for m in vistos]
    assert fechas == sorted(fechas, reverse=True)


def test_movimientos_con_la_misma_fecha_no_se_pierden_ni_repiten(client: Client) -> None:
    usuario, dueno = cuenta()
    for _ in range(3):
        compra(usuario)
    CreditSpend.objects.bulk_create(
        [CreditSpend(user=usuario, amount=1, reason=str(n)) for n in range(4)]
    )
    instante = timezone.now()
    PaymentTransaction.objects.update(created_at=instante)
    CreditSpend.objects.update(created_at=instante)
    cabecera = bearer(usuario, dueno)
    tipos: list[str] = []
    detalles: list[str] = []
    cursor = None
    for _ in range(10):
        parametros = {"limite": 2, **({"cursor": cursor} if cursor else {})}
        pagina = client.get("/api/v1/creditos/movimientos", parametros, **cabecera).json()
        tipos.extend(m["tipo"] for m in pagina["datos"])
        detalles.extend(m["detalle"] for m in pagina["datos"] if m["tipo"] == "consumo")
        cursor = pagina["pagina"]["siguiente_cursor"]
        if cursor is None:
            break
    assert tipos == ["compra"] * 3 + ["consumo"] * 4
    assert sorted(detalles) == list("0123")


def test_un_cursor_manipulado_responde_422(client: Client) -> None:
    from masssend.domain.shared.paginacion import Cursor

    usuario, dueno = cuenta()
    malo = Cursor(("no-es-fecha", "compra", "x")).codificar()
    respuesta = client.get(
        "/api/v1/creditos/movimientos", {"cursor": malo}, **bearer(usuario, dueno)
    )
    assert respuesta.status_code == 422


def test_movimientos_no_hace_mas_consultas_aunque_crezca(client: Client) -> None:
    usuario, dueno = cuenta()
    cabecera = bearer(usuario, dueno)
    CreditSpend.objects.create(user=usuario, amount=1, reason="x")

    def contar(limite: int) -> int:
        with CaptureQueriesContext(connection) as consultas:
            respuesta = client.get("/api/v1/creditos/movimientos", {"limite": limite}, **cabecera)
        assert respuesta.status_code == 200
        return len(consultas)

    con_una_fila = contar(1)
    CreditSpend.objects.bulk_create(
        [CreditSpend(user=usuario, amount=1, reason="x") for _ in range(60)]
    )
    assert contar(50) == con_una_fila
    # Autenticacion (2, por el middleware heredado), dueno, compras y consumos.
    assert con_una_fila <= 5
