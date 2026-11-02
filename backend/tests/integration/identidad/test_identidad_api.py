"""Flujos completos de identidad contra PostgreSQL y adaptadores reales."""

import json
import threading
from datetime import timedelta
from typing import Any
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pyotp
import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import Client
from django.utils import timezone
from rest_framework_simplejwt.tokens import AccessToken

from email_auth.models import EmailTask, SecurityProfile
from masssend.infrastructure.persistence.identidad.models import (
    CuentaIdentidad,
    DesafioIdentidad,
)

pytestmark = pytest.mark.django_db

CLAVE = "clave-larga-123"
Usuario = get_user_model()


def post(client: Client, ruta: str, datos: dict[str, Any] | None = None, **extra: Any) -> Any:
    return client.post(
        f"/api/v1/{ruta}", json.dumps(datos or {}), content_type="application/json", **extra
    )


def es_problema(respuesta: Any, estado: int, codigo: str) -> dict[str, Any]:
    assert respuesta.status_code == estado, respuesta.content
    assert respuesta["Content-Type"] == "application/problem+json"
    cuerpo: dict[str, Any] = respuesta.json()
    assert cuerpo["codigo"] == codigo
    return cuerpo


def bearer(acceso: str) -> dict[str, str]:
    return {"HTTP_AUTHORIZATION": f"Bearer {acceso}"}


def registrar(client: Client, correo: str = "ana@prueba.local") -> str:
    respuesta = post(
        client, "auth/registro", {"nombre": "Ana Lara", "correo": correo, "contrasena": CLAVE}
    )
    assert respuesta.status_code == 201, respuesta.content
    tarea = EmailTask.objects.filter(recipient=correo).latest("created_at")
    codigo: str = tarea.payload["code"]
    return codigo


def activa(client: Client, correo: str = "ana@prueba.local") -> None:
    codigo = registrar(client, correo)
    assert post(client, "auth/verificar", {"correo": correo, "codigo": codigo}).status_code == 200


def login(client: Client, correo: str = "ana@prueba.local", clave: str = CLAVE) -> Any:
    return post(client, "auth/login", {"correo": correo, "contrasena": clave})


def enrolada(client: Client, correo: str = "ana@prueba.local") -> tuple[str, dict[str, Any]]:
    """Cuenta con doble factor. Devuelve el secreto y los tokens."""
    activa(client, correo)
    desafio = login(client, correo).json()["token_desafio"]
    secreto = post(client, "mfa/activar", {"token_desafio": desafio}).json()["clave_manual"]
    respuesta = post(
        client,
        "mfa/confirmar",
        {"token_desafio": desafio, "codigo": pyotp.TOTP(secreto).now()},
    )
    assert respuesta.status_code == 200, respuesta.content
    return secreto, respuesta.json()


def codigo_siguiente(secreto: str, pasos: int = 30) -> str:
    return pyotp.TOTP(secreto).at(timezone.now() + timedelta(seconds=pasos))


def test_el_registro_crea_cuenta_pendiente_compatible_con_el_sistema_actual(
    client: Client,
) -> None:
    registrar(client)
    usuario = Usuario.objects.get(username="ana@prueba.local")
    assert (usuario.email, usuario.first_name, usuario.last_name) == (
        "ana@prueba.local",
        "Ana",
        "Lara",
    )
    assert not usuario.is_active
    assert usuario.check_password(CLAVE)
    assert usuario.security_profile.status == SecurityProfile.STATUS_INACTIVE
    tarea = EmailTask.objects.get(recipient="ana@prueba.local")
    assert tarea.task_type == EmailTask.TYPE_ACCOUNT_VERIFICATION


def test_el_id_publico_es_uuid7(client: Client) -> None:
    respuesta = post(
        client,
        "auth/registro",
        {"nombre": "Ana", "correo": "ana@prueba.local", "contrasena": CLAVE},
    )
    assert respuesta.json()["id"][14] == "7"


@pytest.mark.parametrize(
    ("datos", "campo"),
    [
        ({"correo": "ana@prueba.local", "contrasena": CLAVE}, "nombre"),
        ({"nombre": "Ana", "correo": "mal", "contrasena": CLAVE}, "correo"),
        ({"nombre": "Ana", "correo": "ana@prueba.local", "contrasena": "corta"}, "contrasena"),
    ],
)
def test_el_registro_valida(client: Client, datos: dict[str, str], campo: str) -> None:
    cuerpo = es_problema(post(client, "auth/registro", datos), 422, "datos_invalidos")
    assert campo in json.dumps(cuerpo)


def test_el_correo_activo_no_se_registra_dos_veces(client: Client) -> None:
    activa(client)
    respuesta = post(
        client,
        "auth/registro",
        {"nombre": "Otra", "correo": "ANA@prueba.local", "contrasena": CLAVE},
    )
    es_problema(respuesta, 409, "estado_invalido")


def test_los_intentos_de_verificacion_persisten_y_el_sexto_responde_429(client: Client) -> None:
    registrar(client)
    datos = {"correo": "ana@prueba.local", "codigo": "000000"}
    for _ in range(5):
        es_problema(post(client, "auth/verificar", datos), 422, "datos_invalidos")
    es_problema(post(client, "auth/verificar", datos), 429, "demasiados_intentos")


def test_un_codigo_vencido_se_rechaza(client: Client) -> None:
    codigo = registrar(client)
    SecurityProfile.objects.update(verification_code_expires_at=timezone.now())
    respuesta = post(client, "auth/verificar", {"correo": "ana@prueba.local", "codigo": codigo})
    es_problema(respuesta, 422, "datos_invalidos")


def test_reenviar_responde_igual_exista_o_no_la_cuenta(client: Client) -> None:
    primero = registrar(client)
    existe = post(client, "auth/reenviar-codigo", {"correo": "ana@prueba.local"})
    nadie = post(client, "auth/reenviar-codigo", {"correo": "nadie@prueba.local"})
    assert existe.status_code == nadie.status_code == 202
    assert existe.content == nadie.content
    assert EmailTask.objects.count() == 2
    respuesta = post(client, "auth/verificar", {"correo": "ana@prueba.local", "codigo": primero})
    assert respuesta.status_code in (200, 422)


def test_sin_verificar_no_se_inicia_sesion(client: Client) -> None:
    registrar(client)
    es_problema(login(client), 401, "no_autenticado")


def test_login_incorrecto_responde_igual_que_cuenta_inexistente(client: Client) -> None:
    activa(client)
    mala = login(client, clave="incorrecta")
    nadie = login(client, correo="nadie@prueba.local")
    es_problema(mala, 401, "no_autenticado")
    assert mala.json()["detail"] == nadie.json()["detail"]


def test_la_cuenta_nueva_debe_enrolarse_y_recibe_tokens_al_terminar(client: Client) -> None:
    activa(client)
    paso = login(client).json()
    assert paso["siguiente"] == "activar_mfa"
    assert "acceso" not in paso
    desafio = paso["token_desafio"]
    iniciado = post(client, "mfa/activar", {"token_desafio": desafio}).json()
    assert iniciado["qr"].startswith("data:image/png;base64,")
    assert iniciado["uri"].startswith("otpauth://totp/")
    malo = post(client, "mfa/confirmar", {"token_desafio": desafio, "codigo": "000000"})
    es_problema(malo, 422, "datos_invalidos")
    respuesta = post(
        client,
        "mfa/confirmar",
        {"token_desafio": desafio, "codigo": pyotp.TOTP(iniciado["clave_manual"]).now()},
    )
    assert respuesta.status_code == 200
    assert client.get("/api/v1/mfa/estado", **bearer(respuesta.json()["acceso"])).json() == {
        "activo": True
    }


def test_el_token_de_desafio_se_guarda_con_hash(client: Client) -> None:
    activa(client)
    token = login(client).json()["token_desafio"]
    assert not DesafioIdentidad.objects.filter(hash_token=token).exists()
    assert DesafioIdentidad.objects.count() == 1


def test_el_login_completo_entrega_jwt_de_vida_corta_con_id_publico(client: Client) -> None:
    secreto, _ = enrolada(client)
    desafio = login(client).json()
    assert desafio["siguiente"] == "totp"
    tokens = post(
        client,
        "auth/login/totp",
        {"token_desafio": desafio["token_desafio"], "codigo": codigo_siguiente(secreto)},
    ).json()
    acceso = AccessToken(tokens["acceso"])
    identidad = CuentaIdentidad.objects.get()
    assert acceso["public_id"] == str(identidad.public_id)
    assert acceso["exp"] - acceso["iat"] == 15 * 60
    perfil = client.get("/api/v1/auth/yo", **bearer(tokens["acceso"]))
    assert perfil.status_code == 200
    assert perfil.json() == {
        "id": str(identidad.public_id),
        "nombre": "Ana Lara",
        "correo": "ana@prueba.local",
        "mfa_activo": True,
        "es_staff": False,
    }


def test_totp_sin_desafio_responde_401(client: Client) -> None:
    respuesta = post(client, "auth/login/totp", {"token_desafio": "falso", "codigo": "123456"})
    es_problema(respuesta, 401, "no_autenticado")


def test_el_desafio_es_de_un_solo_uso(client: Client) -> None:
    secreto, _ = enrolada(client)
    token = login(client).json()["token_desafio"]
    datos = {"token_desafio": token, "codigo": codigo_siguiente(secreto)}
    assert post(client, "auth/login/totp", datos).status_code == 200
    es_problema(post(client, "auth/login/totp", datos), 401, "no_autenticado")


def test_un_codigo_reutilizado_responde_401(client: Client) -> None:
    secreto, _ = enrolada(client)
    codigo = codigo_siguiente(secreto)
    primero = login(client).json()["token_desafio"]
    datos = {"token_desafio": primero, "codigo": codigo}
    assert post(client, "auth/login/totp", datos).status_code == 200
    segundo = login(client).json()["token_desafio"]
    respuesta = post(client, "auth/login/totp", {"token_desafio": segundo, "codigo": codigo})
    es_problema(respuesta, 401, "no_autenticado")


def test_el_codigo_con_el_que_se_activo_no_sirve_para_entrar(client: Client) -> None:
    activa(client)
    desafio = login(client).json()["token_desafio"]
    secreto = post(client, "mfa/activar", {"token_desafio": desafio}).json()["clave_manual"]
    codigo = pyotp.TOTP(secreto).now()
    post(client, "mfa/confirmar", {"token_desafio": desafio, "codigo": codigo})
    token = login(client).json()["token_desafio"]
    respuesta = post(client, "auth/login/totp", {"token_desafio": token, "codigo": codigo})
    es_problema(respuesta, 401, "no_autenticado")


def test_el_sexto_intento_responde_429_aunque_se_pida_otro_desafio(client: Client) -> None:
    secreto, _ = enrolada(client)
    for _ in range(5):
        token = login(client).json()["token_desafio"]
        respuesta = post(client, "auth/login/totp", {"token_desafio": token, "codigo": "000000"})
        es_problema(respuesta, 401, "no_autenticado")
    token = login(client).json()["token_desafio"]
    respuesta = post(
        client,
        "auth/login/totp",
        {"token_desafio": token, "codigo": codigo_siguiente(secreto)},
    )
    cuerpo = es_problema(respuesta, 429, "demasiados_intentos")
    assert cuerpo["espera_segundos"] > 0
    assert int(respuesta["Retry-After"]) == cuerpo["espera_segundos"]


def test_renovar_rota_y_el_token_viejo_ya_no_sirve(client: Client) -> None:
    _, tokens = enrolada(client)
    nuevo = post(client, "auth/token/renovar", {"renovacion": tokens["renovacion"]})
    assert nuevo.status_code == 200
    assert AccessToken(nuevo.json()["acceso"])["public_id"]
    viejo = post(client, "auth/token/renovar", {"renovacion": tokens["renovacion"]})
    es_problema(viejo, 401, "no_autenticado")


def test_renovar_con_un_token_de_acceso_se_rechaza(client: Client) -> None:
    _, tokens = enrolada(client)
    respuesta = post(client, "auth/token/renovar", {"renovacion": tokens["acceso"]})
    es_problema(respuesta, 401, "no_autenticado")


def test_una_cuenta_desactivada_no_renueva(client: Client) -> None:
    _, tokens = enrolada(client)
    Usuario.objects.update(is_active=False)
    respuesta = post(client, "auth/token/renovar", {"renovacion": tokens["renovacion"]})
    es_problema(respuesta, 401, "no_autenticado")


def test_logout_revoca_la_renovacion(client: Client) -> None:
    _, tokens = enrolada(client)
    respuesta = post(
        client, "auth/logout", {"renovacion": tokens["renovacion"]}, **bearer(tokens["acceso"])
    )
    assert respuesta.status_code == 204
    otra = post(client, "auth/token/renovar", {"renovacion": tokens["renovacion"]})
    es_problema(otra, 401, "no_autenticado")


def test_logout_exige_sesion(client: Client) -> None:
    es_problema(post(client, "auth/logout", {"renovacion": "x"}), 401, "no_autenticado")


def test_un_jwt_del_sistema_actual_no_entra_en_la_v1(client: Client) -> None:
    activa(client)
    usuario = Usuario.objects.get()
    antiguo = str(AccessToken.for_user(usuario))
    es_problema(client.get("/api/v1/auth/yo", **bearer(antiguo)), 401, "no_autenticado")


def test_rutas_protegidas_exigen_token(client: Client) -> None:
    for ruta in ("auth/yo", "mfa/estado"):
        es_problema(client.get(f"/api/v1/{ruta}"), 401, "no_autenticado")
    es_problema(post(client, "mfa/activar"), 401, "no_autenticado")
    es_problema(post(client, "mfa/desactivar", {"contrasena": "x"}), 401, "no_autenticado")


def test_desactivar_exige_contrasena_y_vuelve_a_pedir_enrolamiento(client: Client) -> None:
    _, tokens = enrolada(client)
    cabecera = bearer(tokens["acceso"])
    mala = post(client, "mfa/desactivar", {"contrasena": "incorrecta"}, **cabecera)
    es_problema(mala, 422, "datos_invalidos")
    assert post(client, "mfa/desactivar", {"contrasena": CLAVE}, **cabecera).json() == {
        "activo": False
    }
    assert login(client).json()["siguiente"] == "activar_mfa"


def test_con_doble_factor_activo_no_se_reemplaza_el_secreto(client: Client) -> None:
    _, tokens = enrolada(client)
    es_problema(post(client, "mfa/activar", **bearer(tokens["acceso"])), 409, "estado_invalido")


def test_un_desafio_de_totp_no_sirve_para_enrolar(client: Client) -> None:
    enrolada(client)
    token = login(client).json()["token_desafio"]
    es_problema(post(client, "mfa/activar", {"token_desafio": token}), 401, "no_autenticado")


def token_recuperacion() -> str:
    url = EmailTask.objects.filter(task_type=EmailTask.TYPE_PASSWORD_RECOVERY).latest(
        "created_at"
    ).payload["resetUrl"]
    return parse_qs(urlparse(url).query)["token"][0]


def test_recuperar_no_revela_cuentas(client: Client) -> None:
    activa(client)
    existe = post(client, "auth/recuperar", {"correo": "ana@prueba.local"})
    nadie = post(client, "auth/recuperar", {"correo": "nadie@prueba.local"})
    assert existe.status_code == nadie.status_code == 202
    assert existe.content == nadie.content


def test_restablecer_cambia_la_clave_y_revoca_las_sesiones(client: Client) -> None:
    _, tokens = enrolada(client)
    post(client, "auth/recuperar", {"correo": "ana@prueba.local"})
    token = token_recuperacion()
    assert not DesafioIdentidad.objects.filter(hash_token=token).exists()
    datos = {"token": token, "nueva_contrasena": "clave-nueva-456"}
    assert post(client, "auth/restablecer", datos).status_code == 200
    es_problema(post(client, "auth/restablecer", datos), 401, "no_autenticado")
    es_problema(login(client), 401, "no_autenticado")
    assert login(client, clave="clave-nueva-456").status_code == 200
    viejo = post(client, "auth/token/renovar", {"renovacion": tokens["renovacion"]})
    es_problema(viejo, 401, "no_autenticado")


def test_cambiar_contrasena_exige_la_actual_y_revoca(client: Client) -> None:
    _, tokens = enrolada(client)
    cabecera = bearer(tokens["acceso"])
    malo = {"contrasena_actual": "incorrecta", "nueva_contrasena": "clave-nueva-456"}
    es_problema(post(client, "auth/cambiar-contrasena", malo, **cabecera), 422, "datos_invalidos")
    bueno = {"contrasena_actual": CLAVE, "nueva_contrasena": "clave-nueva-456"}
    assert post(client, "auth/cambiar-contrasena", bueno, **cabecera).status_code == 200
    assert login(client, clave="clave-nueva-456").status_code == 200
    viejo = post(client, "auth/token/renovar", {"renovacion": tokens["renovacion"]})
    es_problema(viejo, 401, "no_autenticado")


def flujo_google(client: Client, correo: str = "ana") -> Any:
    url = client.get("/api/v1/auth/google").json()["url"]
    estado = parse_qs(urlparse(url).query)["state"][0]
    return client.get("/api/v1/auth/google/callback", {"state": estado, "code": correo})


@pytest.fixture
def google_falso(settings: Any) -> None:
    settings.PROVEEDOR_GOOGLE = "fake"


@pytest.mark.usefixtures("google_falso")
def test_google_crea_cuenta_y_aun_exige_doble_factor(client: Client) -> None:
    respuesta = flujo_google(client)
    assert respuesta.status_code == 200
    assert respuesta.json()["siguiente"] == "activar_mfa"
    usuario = Usuario.objects.get(username="ana@google.prueba")
    assert usuario.is_active
    assert not usuario.has_usable_password()


@pytest.mark.usefixtures("google_falso")
def test_google_rechaza_un_estado_falso(client: Client) -> None:
    respuesta = client.get("/api/v1/auth/google/callback", {"state": "falso", "code": "ana"})
    es_problema(respuesta, 401, "no_autenticado")


@pytest.mark.usefixtures("google_falso")
def test_google_borra_la_contrasena_de_una_cuenta_pendiente_ajena(client: Client) -> None:
    registrar(client, "ana@google.prueba")
    assert flujo_google(client).status_code == 200
    es_problema(login(client, "ana@google.prueba"), 401, "no_autenticado")


def test_la_url_real_de_google_lleva_el_estado_y_el_retorno(client: Client, settings: Any) -> None:
    settings.PROVEEDOR_GOOGLE = "google"
    settings.GOOGLE_CLIENT_ID = "cliente"
    url = urlparse(client.get("/api/v1/auth/google").json()["url"])
    consulta = parse_qs(url.query)
    assert url.netloc == "accounts.google.com"
    assert consulta["client_id"] == ["cliente"]
    assert consulta["redirect_uri"] == [settings.GOOGLE_RETORNO_V1]
    assert consulta["state"]


def test_si_google_falla_responde_503(client: Client, settings: Any) -> None:
    import requests as biblioteca

    settings.PROVEEDOR_GOOGLE = "google"
    url = client.get("/api/v1/auth/google").json()["url"]
    estado = parse_qs(urlparse(url).query)["state"][0]
    ruta = "masssend.infrastructure.adapters.google.oauth.requests.post"
    with patch(ruta, side_effect=biblioteca.ConnectionError):
        respuesta = client.get(
            "/api/v1/auth/google/callback", {"state": estado, "code": "x"}
        )
    es_problema(respuesta, 503, "servicio_no_disponible")


def test_un_administrador_existente_entra_por_su_usuario(client: Client) -> None:
    Usuario.objects.create_superuser("admin", password=CLAVE)
    paso = login(client, correo="admin")
    assert paso.status_code == 200
    assert paso.json()["siguiente"] == "activar_mfa"
    perfil = SecurityProfile.objects.get(user__username="admin")
    assert perfil.status == SecurityProfile.STATUS_ACTIVE


def test_el_login_actual_sigue_viendo_la_cuenta_creada_en_la_v1(client: Client) -> None:
    activa(client)
    from django.contrib.auth import authenticate

    assert authenticate(username="ana@prueba.local", password=CLAVE) is not None


@pytest.mark.django_db(transaction=True)
def test_dos_totp_simultaneos_con_el_mismo_codigo_solo_uno_entra() -> None:
    client = Client()
    secreto, _ = enrolada(client)
    codigo = codigo_siguiente(secreto)
    desafios = [login(client).json()["token_desafio"] for _ in range(2)]
    estados: list[int] = []
    barrera = threading.Barrier(2)

    def intentar(token: str) -> None:
        try:
            barrera.wait()
            respuesta = post(
                Client(), "auth/login/totp", {"token_desafio": token, "codigo": codigo}
            )
            estados.append(respuesta.status_code)
        finally:
            connection.close()

    hilos = [threading.Thread(target=intentar, args=(token,)) for token in desafios]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join()
    assert sorted(estados) == [200, 401]


def test_las_rutas_sensibles_tienen_limite_por_ip(client: Client) -> None:
    from django.core.cache import cache

    from masssend.interfaces.http.shared.limites import LimiteSensible

    cache.clear()
    with patch.dict(LimiteSensible.THROTTLE_RATES, {"sensible_v1": "2/min"}):
        for _ in range(2):
            es_problema(login(client), 401, "no_autenticado")
        es_problema(login(client), 429, "demasiados_intentos")
    cache.clear()
