from datetime import timedelta

import pytest

from masssend.application.identidad.google import CompletarGoogle, IniciarGoogle
from masssend.application.identidad.mfa import (
    ActivarMfa,
    ConfirmarMfa,
    ConsultarMfa,
    DesactivarMfa,
    ResolverCuentaEnrolamiento,
)
from masssend.application.identidad.puertos import (
    IColaCorreos,
    IEmisorTokens,
    IHasherContrasenas,
    ITotp,
    PerfilGoogle,
)
from masssend.application.identidad.recuperacion import (
    CambiarContrasena,
    RestablecerContrasena,
    SolicitarRecuperacion,
)
from masssend.application.identidad.registro import (
    ReenviarCodigo,
    RegistrarCuenta,
    VerificarCuenta,
)
from masssend.application.identidad.sesion import (
    CerrarSesion,
    ConsultarPerfil,
    IniciarSesion,
    RenovarToken,
    ValidarTotp,
)
from masssend.domain.identidad.desafio import Proposito
from masssend.domain.identidad.repositorios import IRepoCuentas, IRepoDesafios
from masssend.domain.shared.errores import (
    DatosInvalidos,
    DemasiadosIntentos,
    EstadoInvalido,
    NoAutenticado,
    RecursoNoEncontrado,
)
from tests.fakes.identidad import ProveedorGoogleFalso
from tests.unit.identidad.entorno import VIGENCIA, Entorno

CORREO = "ana@prueba.local"
CLAVE = "clave-larga"


@pytest.fixture
def e() -> Entorno:
    return Entorno()


def registrar(e: Entorno) -> RegistrarCuenta:
    return RegistrarCuenta(
        e.cuentas, e.hasher, e.cola, e.uow, e.reloj, e.ids, e.aleatorio, VIGENCIA
    )


def login(e: Entorno) -> IniciarSesion:
    return IniciarSesion(e.cuentas, e.hasher, e.desafios, e.uow)


def totp(e: Entorno) -> ValidarTotp:
    return ValidarTotp(e.cuentas, e.desafios, e.totp, e.tokens, e.uow, e.reloj)


def confirmar(e: Entorno) -> ConfirmarMfa:
    return ConfirmarMfa(e.cuentas, e.desafios, e.totp, e.tokens, e.uow, e.reloj)


def test_los_fakes_cumplen_los_puertos(e: Entorno) -> None:
    cuentas: IRepoCuentas = e.cuentas
    desafios: IRepoDesafios = e.repo_desafios
    hasher: IHasherContrasenas = e.hasher
    motor: ITotp = e.totp
    cola: IColaCorreos = e.cola
    tokens: IEmisorTokens = e.tokens
    assert all((cuentas, desafios, hasher, motor, cola, tokens))


def test_registrar_crea_pendiente_y_encola_el_codigo(e: Entorno) -> None:
    creada = registrar(e).ejecutar(" Ana ", " ANA@Prueba.local ", CLAVE)
    cuenta = e.cuentas.obtener(creada.id)
    assert (cuenta.correo, cuenta.nombre, cuenta.activa) == (CORREO, "Ana", False)
    assert cuenta.hash_contrasena == f"hash:{CLAVE}"
    assert e.cola.codigos == [(CORREO, "111111")]


@pytest.mark.parametrize(
    ("nombre", "correo", "clave", "campo"),
    [
        ("  ", CORREO, CLAVE, "nombre"),
        ("Ana", "mal", CLAVE, "correo"),
        ("Ana", CORREO, "corta", "contrasena"),
    ],
)
def test_registrar_valida_cada_campo(
    e: Entorno, nombre: str, correo: str, clave: str, campo: str
) -> None:
    with pytest.raises(DatosInvalidos) as error:
        registrar(e).ejecutar(nombre, correo, clave)
    assert error.value.campo == campo


def test_no_se_registra_una_cuenta_activa(e: Entorno) -> None:
    e.cuenta()
    with pytest.raises(EstadoInvalido):
        registrar(e).ejecutar("Otra", CORREO, CLAVE)


def test_registrar_de_nuevo_una_pendiente_reutiliza_la_cuenta(e: Entorno) -> None:
    primera = registrar(e).ejecutar("Ana", CORREO, CLAVE)
    segunda = registrar(e).ejecutar("Ana Maria", CORREO, "otra-clave")
    assert primera.id == segunda.id
    assert len(e.cuentas.cuentas) == 1


def test_verificar_activa_la_cuenta(e: Entorno) -> None:
    creada = registrar(e).ejecutar("Ana", CORREO, CLAVE)
    VerificarCuenta(e.cuentas, e.uow, e.reloj).ejecutar(CORREO, "111111")
    assert e.cuentas.obtener(creada.id).activa


def test_un_codigo_incorrecto_guarda_el_intento(e: Entorno) -> None:
    creada = registrar(e).ejecutar("Ana", CORREO, CLAVE)
    with pytest.raises(DatosInvalidos):
        VerificarCuenta(e.cuentas, e.uow, e.reloj).ejecutar(CORREO, "000000")
    assert e.cuentas.obtener(creada.id).intentos_verificacion == 1


def test_un_correo_desconocido_no_se_distingue_de_un_codigo_malo(e: Entorno) -> None:
    with pytest.raises(DatosInvalidos) as error:
        VerificarCuenta(e.cuentas, e.uow, e.reloj).ejecutar("nadie@prueba.local", "000000")
    assert error.value.mensaje == "El código es incorrecto."


def test_reenviar_solo_actua_sobre_pendientes(e: Entorno) -> None:
    reenviar = ReenviarCodigo(e.cuentas, e.cola, e.uow, e.reloj, e.aleatorio, VIGENCIA)
    reenviar.ejecutar("nadie@prueba.local")
    assert e.cola.codigos == []
    registrar(e).ejecutar("Ana", CORREO, CLAVE)
    reenviar.ejecutar(CORREO)
    assert len(e.cola.codigos) == 2


def test_la_contrasena_nunca_entrega_tokens(e: Entorno) -> None:
    e.cuenta_con_mfa()
    paso = login(e).ejecutar(CORREO, CLAVE)
    assert paso.siguiente == "totp"
    assert e.tokens.vigentes == {}


def test_sin_doble_factor_exige_enrolarse(e: Entorno) -> None:
    e.cuenta()
    assert login(e).ejecutar(CORREO, CLAVE).siguiente == "activar_mfa"


@pytest.mark.parametrize(
    ("correo", "clave"), [(CORREO, "incorrecta"), ("nadie@prueba.local", CLAVE)]
)
def test_las_credenciales_malas_dan_el_mismo_error(e: Entorno, correo: str, clave: str) -> None:
    e.cuenta()
    with pytest.raises(NoAutenticado) as error:
        login(e).ejecutar(correo, clave)
    assert error.value.mensaje == "Correo o contraseña incorrectos."


def test_una_cuenta_sin_verificar_no_inicia_sesion(e: Entorno) -> None:
    e.cuenta(activa=False)
    with pytest.raises(NoAutenticado):
        login(e).ejecutar(CORREO, CLAVE)


def test_el_totp_correcto_entrega_tokens(e: Entorno) -> None:
    cuenta = e.cuenta_con_mfa()
    paso = login(e).ejecutar(CORREO, CLAVE)
    par = totp(e).ejecutar(paso.token_desafio, "100001")
    assert e.tokens.vigentes[par.renovacion] == cuenta.id


def test_el_desafio_no_sirve_dos_veces(e: Entorno) -> None:
    e.cuenta_con_mfa()
    paso = login(e).ejecutar(CORREO, CLAVE)
    totp(e).ejecutar(paso.token_desafio, "100001")
    with pytest.raises(NoAutenticado):
        totp(e).ejecutar(paso.token_desafio, "100002")


def test_sin_desafio_valido_no_se_acepta_el_codigo(e: Entorno) -> None:
    with pytest.raises(NoAutenticado):
        totp(e).ejecutar("inventado", "100001")


def test_el_desafio_vencido_no_se_acepta(e: Entorno) -> None:
    e.cuenta_con_mfa()
    paso = login(e).ejecutar(CORREO, CLAVE)
    e.reloj.avanzar(timedelta(minutes=5))
    with pytest.raises(NoAutenticado):
        totp(e).ejecutar(paso.token_desafio, "100001")


def test_un_desafio_de_enrolamiento_no_sirve_para_totp(e: Entorno) -> None:
    e.cuenta()
    paso = login(e).ejecutar(CORREO, CLAVE)
    with pytest.raises(NoAutenticado):
        totp(e).ejecutar(paso.token_desafio, "100001")


def test_un_codigo_repetido_se_rechaza(e: Entorno) -> None:
    e.cuenta_con_mfa()
    totp(e).ejecutar(login(e).ejecutar(CORREO, CLAVE).token_desafio, "100001")
    with pytest.raises(NoAutenticado):
        totp(e).ejecutar(login(e).ejecutar(CORREO, CLAVE).token_desafio, "100001")


def test_el_sexto_intento_responde_demasiados_intentos(e: Entorno) -> None:
    e.cuenta_con_mfa()
    paso = login(e).ejecutar(CORREO, CLAVE)
    for _ in range(5):
        with pytest.raises(NoAutenticado):
            totp(e).ejecutar(paso.token_desafio, "000000")
    with pytest.raises(DemasiadosIntentos):
        totp(e).ejecutar(paso.token_desafio, "100001")


def test_un_desafio_nuevo_no_evade_el_bloqueo(e: Entorno) -> None:
    e.cuenta_con_mfa()
    for _ in range(5):
        with pytest.raises(NoAutenticado):
            totp(e).ejecutar(login(e).ejecutar(CORREO, CLAVE).token_desafio, "000000")
    with pytest.raises(DemasiadosIntentos):
        totp(e).ejecutar(login(e).ejecutar(CORREO, CLAVE).token_desafio, "100001")


def test_el_bloqueo_termina_a_los_quince_minutos(e: Entorno) -> None:
    e.cuenta_con_mfa()
    for _ in range(5):
        with pytest.raises(NoAutenticado):
            totp(e).ejecutar(login(e).ejecutar(CORREO, CLAVE).token_desafio, "000000")
    e.reloj.avanzar(timedelta(minutes=15))
    assert totp(e).ejecutar(login(e).ejecutar(CORREO, CLAVE).token_desafio, "100001")


def test_el_enrolamiento_completo_entrega_tokens(e: Entorno) -> None:
    cuenta = e.cuenta()
    paso = login(e).ejecutar(CORREO, CLAVE)
    resuelta = ResolverCuentaEnrolamiento(e.desafios, e.uow).ejecutar(paso.token_desafio)
    assert resuelta == cuenta.id
    iniciado = ActivarMfa(e.cuentas, e.totp, e.uow).ejecutar(resuelta)
    assert iniciado.clave_manual == "SECRETO"
    assert iniciado.qr.startswith("data:")
    par = confirmar(e).ejecutar(resuelta, "100001", paso.token_desafio)
    assert par is not None
    assert ConsultarMfa(e.cuentas).ejecutar(resuelta)


def test_el_codigo_de_activacion_no_sirve_para_entrar(e: Entorno) -> None:
    cuenta = e.cuenta(mfa_secreto_pendiente="SECRETO")
    confirmar(e).ejecutar(cuenta.id, "100001")
    with pytest.raises(NoAutenticado):
        totp(e).ejecutar(login(e).ejecutar(CORREO, CLAVE).token_desafio, "100001")


def test_confirmar_sin_activar_o_con_codigo_malo_falla(e: Entorno) -> None:
    cuenta = e.cuenta()
    with pytest.raises(EstadoInvalido):
        confirmar(e).ejecutar(cuenta.id, "100001")
    ActivarMfa(e.cuentas, e.totp, e.uow).ejecutar(cuenta.id)
    with pytest.raises(DatosInvalidos):
        confirmar(e).ejecutar(cuenta.id, "000000")
    assert not e.cuentas.obtener(cuenta.id).mfa_activo


def test_activar_no_pisa_un_doble_factor_vigente(e: Entorno) -> None:
    cuenta = e.cuenta_con_mfa()
    with pytest.raises(EstadoInvalido):
        ActivarMfa(e.cuentas, e.totp, e.uow).ejecutar(cuenta.id)


def test_desactivar_exige_la_contrasena(e: Entorno) -> None:
    cuenta = e.cuenta_con_mfa()
    desactivar = DesactivarMfa(e.cuentas, e.hasher, e.uow)
    with pytest.raises(DatosInvalidos):
        desactivar.ejecutar(cuenta.id, "incorrecta")
    assert e.cuentas.obtener(cuenta.id).mfa_activo
    desactivar.ejecutar(cuenta.id, CLAVE)
    assert not e.cuentas.obtener(cuenta.id).mfa_activo


def test_renovar_rota_y_cerrar_revoca(e: Entorno) -> None:
    cuenta = e.cuenta()
    par = e.tokens.emitir(cuenta.id)
    nuevo = RenovarToken(e.tokens).ejecutar(par.renovacion)
    with pytest.raises(NoAutenticado):
        RenovarToken(e.tokens).ejecutar(par.renovacion)
    CerrarSesion(e.tokens).ejecutar(nuevo.renovacion)
    with pytest.raises(NoAutenticado):
        RenovarToken(e.tokens).ejecutar(nuevo.renovacion)


def test_el_perfil_no_incluye_secretos(e: Entorno) -> None:
    perfil = ConsultarPerfil(e.cuentas).ejecutar(e.cuenta_con_mfa().id)
    assert perfil.correo == CORREO
    assert not hasattr(perfil, "mfa_secreto")
    assert not hasattr(perfil, "hash_contrasena")


def test_un_perfil_inexistente_responde_no_encontrado(e: Entorno) -> None:
    with pytest.raises(RecursoNoEncontrado):
        ConsultarPerfil(e.cuentas).ejecutar(e.ids.nuevo())


def recuperar(e: Entorno) -> SolicitarRecuperacion:
    return SolicitarRecuperacion(e.cuentas, e.repo_desafios, e.desafios, e.cola, e.uow)


def restablecer(e: Entorno) -> RestablecerContrasena:
    return RestablecerContrasena(e.cuentas, e.desafios, e.hasher, e.tokens, e.uow)


def test_recuperar_no_revela_si_la_cuenta_existe(e: Entorno) -> None:
    recuperar(e).ejecutar("nadie@prueba.local")
    assert e.cola.recuperaciones == []


def test_restablecer_cambia_la_clave_y_cierra_las_sesiones(e: Entorno) -> None:
    cuenta = e.cuenta()
    sesion = e.tokens.emitir(cuenta.id)
    recuperar(e).ejecutar(CORREO)
    token = e.cola.recuperaciones[0][1]
    restablecer(e).ejecutar(token, "clave-nueva")
    assert e.cuentas.obtener(cuenta.id).hash_contrasena == "hash:clave-nueva"
    assert sesion.renovacion not in e.tokens.vigentes
    with pytest.raises(NoAutenticado):
        restablecer(e).ejecutar(token, "otra-clave")


def test_un_enlace_nuevo_anula_el_anterior(e: Entorno) -> None:
    e.cuenta()
    recuperar(e).ejecutar(CORREO)
    recuperar(e).ejecutar(CORREO)
    with pytest.raises(NoAutenticado):
        restablecer(e).ejecutar(e.cola.recuperaciones[0][1], "clave-nueva")
    restablecer(e).ejecutar(e.cola.recuperaciones[1][1], "clave-nueva")


def test_cambiar_exige_la_actual_y_cierra_las_sesiones(e: Entorno) -> None:
    cuenta = e.cuenta()
    sesion = e.tokens.emitir(cuenta.id)
    cambiar = CambiarContrasena(e.cuentas, e.hasher, e.tokens, e.uow)
    with pytest.raises(DatosInvalidos):
        cambiar.ejecutar(cuenta.id, "incorrecta", "clave-nueva")
    cambiar.ejecutar(cuenta.id, CLAVE, "clave-nueva")
    assert sesion.renovacion not in e.tokens.vigentes


def google(e: Entorno, verificado: bool = True) -> CompletarGoogle:
    perfil = PerfilGoogle(CORREO, "Ana Google", verificado)
    return CompletarGoogle(
        e.cuentas, ProveedorGoogleFalso(perfil), e.desafios, e.uow, e.ids
    )


def estado_google(e: Entorno) -> str:
    perfil = PerfilGoogle(CORREO, "Ana Google", True)
    url = IniciarGoogle(ProveedorGoogleFalso(perfil), e.desafios, e.uow).ejecutar()
    return url.split("state=")[1]


def test_google_crea_la_cuenta_y_aun_exige_doble_factor(e: Entorno) -> None:
    paso = google(e).ejecutar(estado_google(e), "codigo")
    assert paso.siguiente == "activar_mfa"
    assert e.tokens.vigentes == {}


def test_google_con_cuenta_con_mfa_exige_totp(e: Entorno) -> None:
    e.cuenta_con_mfa()
    assert google(e).ejecutar(estado_google(e), "codigo").siguiente == "totp"


def test_google_rechaza_un_estado_falso_o_repetido(e: Entorno) -> None:
    with pytest.raises(NoAutenticado):
        google(e).ejecutar("inventado", "codigo")
    estado = estado_google(e)
    google(e).ejecutar(estado, "codigo")
    with pytest.raises(NoAutenticado):
        google(e).ejecutar(estado, "codigo")


def test_google_rechaza_correos_sin_verificar(e: Entorno) -> None:
    with pytest.raises(NoAutenticado):
        google(e, verificado=False).ejecutar(estado_google(e), "codigo")


def test_los_propositos_no_se_mezclan(e: Entorno) -> None:
    assert len({proposito.value for proposito in Proposito}) == 4
