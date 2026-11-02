"""La plataforma HTTP de /api/v1/, probada de punta a punta."""

import json
from collections.abc import Iterator
from typing import Any
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client
from rest_framework_simplejwt.tokens import AccessToken

from masssend.domain.shared import errores
from masssend.interfaces.http.shared.limites import LimiteAnonimo
from masssend.interfaces.http.shared.problemas import ERRORES_DOMINIO

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.urls("tests.integration.plataforma.urls_prueba"),
]

PROBLEMA = "application/problem+json"


@pytest.fixture(autouse=True)
def cache_limpia() -> Iterator[None]:
    cache.clear()
    yield
    cache.clear()


def es_problema(respuesta: Any, estado: int, codigo: str) -> dict[str, Any]:
    assert respuesta.status_code == estado
    assert respuesta["Content-Type"] == PROBLEMA
    cuerpo: dict[str, Any] = json.loads(respuesta.content)
    assert cuerpo["status"] == estado
    assert cuerpo["codigo"] == codigo
    assert cuerpo["type"] == f"urn:masssend:problema:{codigo}"
    assert cuerpo["title"] and cuerpo["detail"]
    assert cuerpo["instance"] == respuesta.wsgi_request.path
    return cuerpo


def token(usuario: Any) -> dict[str, str]:
    return {"HTTP_AUTHORIZATION": f"Bearer {AccessToken.for_user(usuario)}"}


def usuario(**datos: Any) -> Any:
    return get_user_model().objects.create_user("ana", password="clave-larga-123", **datos)


def test_salud_informa_api_base_y_version(client: Client) -> None:
    respuesta = client.get("/api/v1/salud")
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["estado"] == "ok"
    assert cuerpo["version"] == "1.0.0"
    assert cuerpo["dependencias"] == {"base_datos": "ok", "cache": "ok"}


def test_salud_responde_503_si_cae_la_base(client: Client) -> None:
    ruta = "masssend.infrastructure.adapters.sistema.salud.connection.cursor"
    with patch(ruta, side_effect=RuntimeError("caida")):
        respuesta = client.get("/api/v1/salud")
    assert respuesta.status_code == 503
    assert respuesta.json()["estado"] == "caido"


@pytest.mark.parametrize(
    "ruta", ["/api/v1/no-existe", "/api/v1/no/existe/tampoco", "/api/v1/salud/", "/api/v1/"]
)
def test_una_ruta_inexistente_responde_problem_json(client: Client, ruta: str) -> None:
    es_problema(client.get(ruta), 404, "recurso_no_encontrado")


def test_metodo_no_permitido(client: Client) -> None:
    es_problema(client.post("/api/v1/salud"), 405, "metodo_no_permitido")


@pytest.mark.parametrize(
    ("nombre", "estado", "codigo"),
    [
        ("datos", 422, "datos_invalidos"),
        ("sesion", 401, "no_autenticado"),
        ("permiso", 403, "sin_permiso"),
        ("ajeno", 404, "recurso_no_encontrado"),
        ("estado", 409, "estado_invalido"),
        ("saldo", 402, "saldo_insuficiente"),
        ("intentos", 429, "demasiados_intentos"),
        ("servicio", 503, "servicio_no_disponible"),
    ],
)
def test_cada_error_de_dominio_tiene_su_respuesta(
    client: Client, nombre: str, estado: int, codigo: str
) -> None:
    es_problema(client.get(f"/api/v1/prueba/error/{nombre}"), estado, codigo)


def test_ningun_error_de_dominio_queda_sin_traducir() -> None:
    clases = {
        c
        for c in vars(errores).values()
        if isinstance(c, type) and issubclass(c, errores.ErrorDominio)
    }
    assert clases - {errores.ErrorDominio} == set(ERRORES_DOMINIO)


def test_los_errores_incluyen_su_detalle(client: Client) -> None:
    assert client.get("/api/v1/prueba/error/datos").json()["campo"] == "nombre"
    saldo = client.get("/api/v1/prueba/error/saldo").json()
    assert (saldo["requerido"], saldo["disponible"]) == (5, 2)
    intentos = client.get("/api/v1/prueba/error/intentos")
    assert intentos["Retry-After"] == "30"
    assert intentos.json()["espera_segundos"] == 30


def test_un_fallo_interno_no_filtra_detalles(client: Client) -> None:
    respuesta = client.get("/api/v1/prueba/fallo")
    es_problema(respuesta, 500, "error_interno")
    assert b"secreto-interno" not in respuesta.content


def test_la_validacion_responde_422_con_cada_campo(client: Client) -> None:
    respuesta = client.post(
        "/api/v1/prueba/validar", {"edad": "x"}, content_type="application/json"
    )
    cuerpo = es_problema(respuesta, 422, "datos_invalidos")
    assert {error["campo"] for error in cuerpo["errores"]} == {"nombre", "edad"}


def test_un_json_mal_formado_responde_400(client: Client) -> None:
    respuesta = client.post("/api/v1/prueba/validar", "{mal", content_type="application/json")
    es_problema(respuesta, 400, "peticion_invalida")


def test_sin_token_responde_401_con_el_esquema(client: Client) -> None:
    respuesta = client.get("/api/v1/prueba/perfil")
    es_problema(respuesta, 401, "no_autenticado")
    assert respuesta["WWW-Authenticate"].startswith("Bearer")


def test_un_token_falso_responde_401(client: Client) -> None:
    respuesta = client.get("/api/v1/prueba/perfil", HTTP_AUTHORIZATION="Bearer falso")
    es_problema(respuesta, 401, "no_autenticado")


def test_la_sesion_de_django_no_autentica_la_v1(client: Client) -> None:
    client.force_login(usuario())
    es_problema(client.get("/api/v1/prueba/perfil"), 401, "no_autenticado")


def test_un_token_valido_entra(client: Client) -> None:
    respuesta = client.get("/api/v1/prueba/perfil", **token(usuario()))
    assert respuesta.status_code == 200
    assert respuesta.json() == {"usuario": "ana"}


def test_sin_permiso_de_staff_responde_403(client: Client) -> None:
    es_problema(client.get("/api/v1/prueba/staff", **token(usuario())), 403, "sin_permiso")


def test_el_limite_responde_429_con_espera(client: Client) -> None:
    with patch.dict(LimiteAnonimo.THROTTLE_RATES, {"anonimo_v1": "2/min"}):
        for _ in range(2):
            assert client.get("/api/v1/prueba/limitada").status_code == 200
        respuesta = client.get("/api/v1/prueba/limitada")
    cuerpo = es_problema(respuesta, 429, "demasiados_intentos")
    assert int(respuesta["Retry-After"]) == cuerpo["espera_segundos"] > 0


def test_falsificar_la_ip_no_evade_el_limite(client: Client) -> None:
    with patch.dict(LimiteAnonimo.THROTTLE_RATES, {"anonimo_v1": "1/min"}):
        client.get("/api/v1/prueba/limitada", HTTP_X_FORWARDED_FOR="1.1.1.1")
        respuesta = client.get("/api/v1/prueba/limitada", HTTP_X_FORWARDED_FOR="2.2.2.2")
    assert respuesta.status_code == 429


def test_si_cae_la_cache_la_api_sigue_respondiendo(client: Client) -> None:
    with patch("rest_framework.throttling.SimpleRateThrottle.cache.get", side_effect=OSError):
        assert client.get("/api/v1/prueba/limitada").status_code == 200


def test_la_paginacion_recorre_todo_por_cursor(client: Client) -> None:
    primera = client.get("/api/v1/prueba/lista", {"limite": 2}).json()
    assert [fila["id"] for fila in primera["datos"]] == [1, 2]
    assert primera["pagina"]["tiene_mas"] is True
    segunda = client.get(
        "/api/v1/prueba/lista",
        {"limite": 10, "cursor": primera["pagina"]["siguiente_cursor"]},
    ).json()
    assert [fila["id"] for fila in segunda["datos"]] == [3, 4, 5]
    assert segunda["pagina"] == {"siguiente_cursor": None, "tiene_mas": False}


@pytest.mark.parametrize(
    "parametros", [{"limite": "x"}, {"limite": 0}, {"limite": 101}, {"cursor": "%%%"}]
)
def test_una_paginacion_invalida_responde_422(client: Client, parametros: dict[str, Any]) -> None:
    es_problema(client.get("/api/v1/prueba/lista", parametros), 422, "datos_invalidos")


def test_la_ruta_actual_de_csrf_sigue_igual(client: Client) -> None:
    assert client.get("/api/csrf/").status_code == 200


def test_las_rutas_actuales_conservan_su_formato_de_error(client: Client) -> None:
    respuesta = client.get("/auth/perfil/")
    assert respuesta.status_code == 401
    assert PROBLEMA not in respuesta["Content-Type"]


def test_las_rutas_actuales_no_tienen_limite_nuevo(client: Client) -> None:
    with patch.dict(LimiteAnonimo.THROTTLE_RATES, {"anonimo_v1": "1/min"}):
        estados = {client.get("/auth/perfil/").status_code for _ in range(3)}
    assert estados == {401}
