from datetime import UTC, datetime, timedelta

import pytest

from masssend.domain.identidad.correo import normalizar_correo, validar_correo
from masssend.domain.identidad.cuenta import Cuenta
from masssend.domain.identidad.desafio import Desafio, Proposito, hash_token
from masssend.domain.identidad.politicas import validar_contrasena
from masssend.domain.shared.errores import (
    DatosInvalidos,
    DemasiadosIntentos,
    EstadoInvalido,
    NoAutenticado,
)
from tests.fakes.ids import GeneradorIdsSecuencial

AHORA = datetime(2026, 1, 1, tzinfo=UTC)
IDS = GeneradorIdsSecuencial()


def cuenta(**datos: object) -> Cuenta:
    nueva = Cuenta(IDS.nuevo(), "ana@prueba.local", "Ana")
    for campo, valor in datos.items():
        setattr(nueva, campo, valor)
    return nueva


def pendiente() -> Cuenta:
    nueva = cuenta()
    nueva.asignar_codigo("123456", AHORA + timedelta(minutes=5))
    return nueva


def test_normaliza_el_correo() -> None:
    assert normalizar_correo("  ANA@Prueba.Local ") == "ana@prueba.local"


@pytest.mark.parametrize("correo", ["", "ana", "ana@", "a b@c.d", "ana@prueba"])
def test_rechaza_correos_mal_formados(correo: str) -> None:
    with pytest.raises(DatosInvalidos):
        validar_correo(correo)


def test_exige_contrasena_de_ocho_caracteres() -> None:
    validar_contrasena("12345678")
    with pytest.raises(DatosInvalidos):
        validar_contrasena("1234567")


def test_un_codigo_correcto_activa_y_borra_el_codigo() -> None:
    nueva = pendiente()
    assert nueva.verificar("123456", AHORA)
    assert nueva.activa
    assert nueva.codigo_verificacion is None


def test_un_codigo_incorrecto_suma_un_intento() -> None:
    nueva = pendiente()
    assert not nueva.verificar("000000", AHORA)
    assert (nueva.activa, nueva.intentos_verificacion) == (False, 1)


def test_un_codigo_vencido_no_activa() -> None:
    with pytest.raises(DatosInvalidos):
        pendiente().verificar("123456", AHORA + timedelta(minutes=5))


def test_el_sexto_intento_de_verificacion_se_bloquea() -> None:
    nueva = pendiente()
    for _ in range(5):
        nueva.verificar("000000", AHORA)
    with pytest.raises(DemasiadosIntentos):
        nueva.verificar("123456", AHORA)


def test_un_codigo_nuevo_reinicia_los_intentos() -> None:
    nueva = pendiente()
    nueva.verificar("000000", AHORA)
    nueva.asignar_codigo("654321", AHORA + timedelta(minutes=5))
    assert nueva.intentos_verificacion == 0


def test_una_cuenta_activa_no_se_verifica_de_nuevo() -> None:
    with pytest.raises(EstadoInvalido):
        cuenta(activa=True).verificar("123456", AHORA)


def test_google_borra_la_contrasena_de_una_cuenta_pendiente() -> None:
    nueva = cuenta(hash_contrasena="de-un-tercero")
    nueva.activar_por_google()
    assert nueva.activa
    assert nueva.hash_contrasena is None


def test_google_conserva_la_contrasena_de_una_cuenta_activa() -> None:
    nueva = cuenta(activa=True, hash_contrasena="propia")
    nueva.activar_por_google()
    assert nueva.hash_contrasena == "propia"


def test_un_paso_nuevo_es_valido_y_uno_repetido_no() -> None:
    nueva = cuenta()
    assert nueva.validar_paso_totp(10, AHORA)
    assert not nueva.validar_paso_totp(10, AHORA)
    assert not nueva.validar_paso_totp(9, AHORA)
    assert nueva.validar_paso_totp(11, AHORA)


def test_cinco_fallos_bloquean_quince_minutos() -> None:
    nueva = cuenta()
    for _ in range(5):
        assert not nueva.validar_paso_totp(None, AHORA)
    with pytest.raises(DemasiadosIntentos) as error:
        nueva.exigir_sin_bloqueo(AHORA)
    assert error.value.espera_segundos == 901
    nueva.exigir_sin_bloqueo(AHORA + timedelta(minutes=15))


def test_un_acierto_limpia_los_fallos() -> None:
    nueva = cuenta()
    nueva.validar_paso_totp(None, AHORA)
    nueva.validar_paso_totp(1, AHORA)
    assert nueva.fallos_totp == 0


def test_el_doble_factor_no_se_activa_dos_veces() -> None:
    with pytest.raises(EstadoInvalido):
        cuenta(mfa_activo=True).iniciar_mfa("OTRO")


def test_confirmar_guarda_el_paso_usado() -> None:
    nueva = cuenta(mfa_secreto_pendiente="SECRETO")
    nueva.confirmar_mfa(7)
    assert (nueva.mfa_secreto, nueva.mfa_secreto_pendiente) == ("SECRETO", None)
    assert not nueva.validar_paso_totp(7, AHORA)


def test_desactivar_exige_que_este_activo() -> None:
    with pytest.raises(EstadoInvalido):
        cuenta().desactivar_mfa()


def test_el_desafio_guarda_hash_y_es_de_un_solo_uso() -> None:
    desafio = Desafio(
        IDS.nuevo(), Proposito.TOTP, hash_token("t"), AHORA + timedelta(minutes=1)
    )
    assert desafio.hash_token != "t"
    desafio.consumir(AHORA)
    with pytest.raises(NoAutenticado):
        desafio.consumir(AHORA)


def test_un_desafio_vencido_no_vale() -> None:
    desafio = Desafio(IDS.nuevo(), Proposito.TOTP, "h", AHORA)
    with pytest.raises(NoAutenticado):
        desafio.exigir_vigente(AHORA)
