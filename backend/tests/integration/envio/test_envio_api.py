"""Envio contra PostgreSQL: lanzar, la cola en base, el trabajador, cancelar y creditos reales."""

import threading
from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest
from django.db import connection
from django.utils import timezone

from billing.models import CreditWallet
from mass_sender.models import Message
from masssend.domain.envio.envio import EstadoEnvio
from masssend.domain.envio.politica import PoliticaEnvio
from masssend.domain.shared.identificadores import IdPublico
from masssend.infrastructure.composition.envio import contenedor_envio
from masssend.infrastructure.persistence.creditos.models import ReservaCreditos
from masssend.infrastructure.persistence.envio.models import EnvioFila, LanzamientoFila
from masssend.interfaces.workers import tareas_envio
from tests.integration.campanas.sesion import Sesion


@pytest.fixture(autouse=True)
def adaptadores_de_prueba(settings: Any) -> None:
    settings.CANAL_MENSAJERIA = "fake"
    settings.COLA_ENVIOS = "sincrona"
    settings.ALMACEN_ARCHIVOS = "memoria"


def con_saldo(nombre: str, saldo: int) -> Sesion:
    sesion = Sesion(nombre)
    CreditWallet.objects.create(user=sesion.usuario, balance=saldo)
    return sesion


def saldo(sesion: Sesion) -> tuple[int, int]:
    """Saldo real y lo que sigue reservado."""
    reservado = sum(
        ReservaCreditos.objects.filter(usuario=sesion.usuario).values_list("restante", flat=True)
    )
    return CreditWallet.objects.get(user=sesion.usuario).balance, reservado


_capturar: list[Any] = []


@pytest.fixture(autouse=True)
def ejecutar_al_confirmar(request: pytest.FixtureRequest) -> None:
    """Las pruebas corren dentro de una transaccion que nunca confirma; esto ejecuta
    lo agendado con al_confirmar, que es donde se publica en la cola."""
    _capturar[:] = []
    if "django_db" in request.keywords and not request.node.get_closest_marker(
        "django_db"
    ).kwargs.get("transaction"):
        _capturar.append(request.getfixturevalue("django_capture_on_commit_callbacks"))


def lanzar(sesion: Sesion, campana: dict[str, Any]) -> Any:
    if not _capturar:
        return sesion.campanas(f"/{campana['id']}/lanzar", "post")
    with _capturar[0](execute=True):
        return sesion.campanas(f"/{campana['id']}/lanzar", "post")


def progreso(sesion: Sesion, campana: dict[str, Any]) -> dict[str, Any]:
    return dict(sesion.campanas(f"/{campana['id']}/progreso").json())


def preparar(sesion: Sesion, cantidad: int = 3) -> dict[str, Any]:
    for i in range(cantidad):
        sesion.crear(f"099111111{i}", nombre=f"Cliente {i}")
    return sesion.crear_campana(mensaje="Hola {{nombre}}")


@pytest.mark.django_db
def test_lanzar_con_la_cola_sincrona_completa_la_campana() -> None:
    ana = con_saldo("ana", 10)
    ana.crear("0991111111", nombre="Pedro")
    ana.crear("0992220000", nombre="Sin WhatsApp")
    baja = ana.crear("0993333333", nombre="Baja")
    ana.patch("/" + baja["id"], {"dado_de_baja": True})
    campana = ana.crear_campana(mensaje="Hola {{nombre}}")
    respuesta = lanzar(ana, campana)
    assert respuesta.status_code == 202
    assert respuesta["Location"] == f"/api/v1/campanas/{campana['id']}/progreso"
    assert respuesta.json()["total"] == 2
    p = progreso(ana, campana)
    assert (p["estado"], p["total"], p["enviados"], p["fallidos"], p["porcentaje"]) == (
        "completada",
        2,
        1,
        1,
        100,
    )
    # Solo se cobra lo que salio; el credito del rechazado vuelve al terminar.
    assert saldo(ana) == (9, 0)
    enviado = EnvioFila.objects.get(estado="enviado")
    assert enviado.texto == "Hola Pedro"
    # El sistema actual ve los mensajes: historial y reportes siguen funcionando.
    estados = sorted(Message.objects.values_list("delivery_status", flat=True))
    assert estados == ["failed", "sent"]
    assert Message.objects.filter(owner=ana.usuario, campaign__isnull=False).count() == 2


@pytest.mark.django_db
def test_sin_saldo_responde_402_y_no_deja_rastro() -> None:
    ana = con_saldo("ana", 2)
    campana = preparar(ana, 3)
    respuesta = lanzar(ana, campana)
    assert respuesta.status_code == 402
    assert (respuesta.json()["requerido"], respuesta.json()["disponible"]) == (3, 2)
    assert ana.campanas("/" + campana["id"]).json()["estado"] == "borrador"
    assert not EnvioFila.objects.exists()
    assert not LanzamientoFila.objects.exists()
    assert saldo(ana) == (2, 0)


@pytest.mark.django_db
def test_lanzar_reglas_de_estado_y_aislamiento() -> None:
    ana = con_saldo("ana", 10)
    luis = con_saldo("luis", 10)
    vacia = ana.crear_campana(etiquetas="nadie")
    assert lanzar(ana, vacia).status_code == 409
    campana = preparar(ana, 1)
    assert lanzar(luis, campana).status_code == 404
    assert luis.campanas(f"/{campana['id']}/progreso").status_code == 404
    assert luis.campanas(f"/{campana['id']}/cancelar", "post").status_code == 404
    assert lanzar(ana, campana).status_code == 202
    assert lanzar(ana, campana).status_code == 409
    assert ana.campanas("/" + campana["id"], "patch", {"nombre": "Otra"}).status_code == 409


@pytest.mark.django_db
def test_sin_whatsapp_responde_503_y_no_cobra(settings: Any) -> None:
    settings.CANAL_MENSAJERIA = "whatsapp"
    settings.WHATSAPP_API_URL = "http://127.0.0.1:9"
    ana = con_saldo("ana", 10)
    campana = preparar(ana, 1)
    respuesta = lanzar(ana, campana)
    assert respuesta.status_code == 503
    assert respuesta["Content-Type"] == "application/problem+json"
    assert saldo(ana) == (10, 0)


@pytest.mark.django_db
def test_la_cola_en_base_programa_con_el_ritmo_y_el_trabajador_envia(settings: Any) -> None:
    settings.COLA_ENVIOS = "base"
    ana = con_saldo("ana", 10)
    campana = preparar(ana, 3)
    assert lanzar(ana, campana).status_code == 202
    assert progreso(ana, campana)["estado"] == "en_curso"
    filas = list(EnvioFila.objects.order_by("orden"))
    inicio = filas[0].programado_para
    assert inicio is not None
    assert [(f.programado_para - inicio).total_seconds() for f in filas] == [0, 3, 6]
    # Solo el primero esta vencido.
    primero = tareas_envio.procesar_siguiente()
    assert primero is not None and primero.estado is EstadoEnvio.ENVIADO
    assert tareas_envio.procesar_siguiente() is None
    EnvioFila.objects.update(programado_para=timezone.now() - timedelta(seconds=1))
    while tareas_envio.procesar_siguiente() is not None:
        pass
    p = progreso(ana, campana)
    assert (p["estado"], p["enviados"], p["pendientes"]) == ("completada", 3, 0)
    assert saldo(ana) == (7, 0)


@pytest.mark.django_db
def test_entregar_dos_veces_el_mismo_trabajo_produce_un_solo_mensaje(settings: Any) -> None:
    settings.COLA_ENVIOS = "base"
    ana = con_saldo("ana", 10)
    campana = preparar(ana, 2)
    lanzar(ana, campana)
    envio_id = IdPublico(EnvioFila.objects.get(orden=0).id)
    procesar = contenedor_envio.procesar_envio()
    primero = procesar.ejecutar(envio_id)
    segundo = contenedor_envio.procesar_envio().ejecutar(envio_id)
    assert primero is not None and not primero.repetido
    assert segundo is not None and segundo.repetido
    assert Message.objects.count() == 1
    assert saldo(ana) == (9, 1)


@pytest.mark.django_db
def test_cancelar_detiene_los_pendientes_y_libera_sus_creditos(settings: Any) -> None:
    settings.COLA_ENVIOS = "base"
    ana = con_saldo("ana", 10)
    campana = preparar(ana, 3)
    lanzar(ana, campana)
    tareas_envio.procesar_siguiente()
    respuesta = ana.campanas(f"/{campana['id']}/cancelar", "post")
    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "campana_id": campana["id"],
        "estado": "cancelada",
        "envios_cancelados": 2,
        "creditos_liberados": 2,
    }
    EnvioFila.objects.update(programado_para=timezone.now() - timedelta(seconds=1))
    assert tareas_envio.procesar_siguiente() is None
    p = progreso(ana, campana)
    assert (p["estado"], p["enviados"], p["cancelados"]) == ("cancelada", 1, 2)
    assert saldo(ana) == (9, 0)
    assert ana.campanas(f"/{campana['id']}/cancelar", "post").status_code == 409


@pytest.mark.django_db
def test_cancelar_un_borrador() -> None:
    ana = con_saldo("ana", 10)
    campana = ana.crear_campana()
    respuesta = ana.campanas(f"/{campana['id']}/cancelar", "post")
    assert respuesta.json()["creditos_liberados"] == 0
    assert progreso(ana, campana)["estado"] == "cancelada"


@pytest.mark.django_db
def test_un_envio_de_una_campana_eliminada_se_ignora(settings: Any) -> None:
    settings.COLA_ENVIOS = "base"
    ana = con_saldo("ana", 10)
    campana = preparar(ana, 1)
    lanzar(ana, campana)
    ana.campanas(f"/{campana['id']}/cancelar", "post")
    assert ana.campanas("/" + campana["id"], "delete").status_code == 204
    assert contenedor_envio.procesar_envio().ejecutar(IdPublico(EnvioFila.objects.get().id))


def test_el_trabajador_respeta_el_ritmo_tras_cada_envio() -> None:
    from masssend.application.envio.procesamiento import EnvioProcesado

    politica = PoliticaEnvio()
    envio_id = _uuid7()
    enviado = EnvioProcesado(envio_id, EstadoEnvio.ENVIADO)
    assert tareas_envio.espera_tras(enviado, politica) == 3
    assert (
        tareas_envio.espera_tras(EnvioProcesado(envio_id, EstadoEnvio.ENVIADO, True), politica) == 0
    )
    assert tareas_envio.espera_tras(EnvioProcesado(envio_id, EstadoEnvio.OMITIDO), politica) == 0
    assert tareas_envio.espera_tras(None, politica) == tareas_envio.ESPERA_SIN_TRABAJO


def _uuid7() -> IdPublico:
    from masssend.infrastructure.composition.root import contenedor

    return contenedor.generador_ids().nuevo()


def en_paralelo(acciones: list[Callable[[], Any]]) -> list[Any]:
    barrera = threading.Barrier(len(acciones))
    resultados: list[Any] = []

    def correr(accion: Callable[[], Any]) -> None:
        try:
            barrera.wait()
            resultados.append(accion())
        finally:
            connection.close()

    hilos = [threading.Thread(target=correr, args=(a,)) for a in acciones]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join()
    return resultados


@pytest.mark.django_db(transaction=True)
def test_dos_lanzamientos_simultaneos_con_saldo_para_uno() -> None:
    """La condicion de Anderson para creditos: un 202 y un 402."""
    ana = con_saldo("ana", 5)
    for i in range(3):
        ana.crear(f"099111111{i}")
    primera = ana.crear_campana(nombre="Primera")
    segunda = ana.crear_campana(nombre="Segunda")
    codigos = en_paralelo(
        [lambda: lanzar(ana, primera).status_code, lambda: lanzar(ana, segunda).status_code]
    )
    assert sorted(codigos) == [202, 402]
    assert saldo(ana) == (2, 0)
