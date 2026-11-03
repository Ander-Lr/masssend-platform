from collections.abc import Iterator

import pytest

from masssend.application.campanas.importacion import (
    FilaImportacion,
    ImportarContactos,
    ResultadoImportacion,
)
from masssend.domain.shared.identificadores import IdPublico
from tests.fakes.campanas import RepoContactosMemoria
from tests.fakes.ids import GeneradorIdsSecuencial
from tests.fakes.unidad_de_trabajo import UnidadDeTrabajoFalsa

IDS = GeneradorIdsSecuencial()
ANA = IDS.nuevo()
LUIS = IDS.nuevo()


def importar(
    repo: RepoContactosMemoria,
    filas: list[FilaImportacion] | Iterator[FilaImportacion],
    dueno: IdPublico = ANA,
    lote: int = 500,
) -> ResultadoImportacion:
    caso = ImportarContactos(repo, IDS, UnidadDeTrabajoFalsa(), tamano_lote=lote)
    return caso.ejecutar(dueno, filas)


def fila(numero: int, telefono: str, nombre: str = "", **extra: str) -> FilaImportacion:
    return FilaImportacion(numero, telefono, nombre, **extra)


def test_importar_normaliza_y_crea() -> None:
    repo = RepoContactosMemoria()
    resultado = importar(repo, [fila(1, "0991112222", "Pedro", etiquetas="vip")])
    assert (resultado.creados, resultado.actualizados, resultado.total) == (1, 0, 1)
    (contacto,) = repo.contactos.values()
    assert contacto.telefono.numero == "593991112222"
    assert contacto.etiquetas == ("vip",)


def test_las_filas_invalidas_se_informan_y_no_detienen_el_resto() -> None:
    repo = RepoContactosMemoria()
    resultado = importar(
        repo,
        [fila(2, "0991112222"), fila(3, "022345678"), fila(4, ""), fila(5, "0992223333")],
    )
    assert resultado.creados == 2
    assert [(r.numero, r.campo) for r in resultado.rechazadas] == [
        (3, "telefono"),
        (4, "telefono"),
    ]
    assert resultado.rechazadas[0].telefono == "022345678"
    assert "fijo" in resultado.rechazadas[0].mensaje
    assert resultado.total == 4


def test_un_numero_existente_se_actualiza() -> None:
    repo = RepoContactosMemoria()
    importar(repo, [fila(1, "0991112222", "Pedro")])
    resultado = importar(repo, [fila(1, "+593 99 111 2222", "Pedro Pérez", notas="cliente fiel")])
    assert (resultado.creados, resultado.actualizados) == (0, 1)
    (contacto,) = repo.contactos.values()
    assert contacto.nombre == "Pedro Pérez"
    assert contacto.datos == {"notas": "cliente fiel"}


def test_un_numero_repetido_en_el_archivo_no_se_duplica() -> None:
    repo = RepoContactosMemoria()
    resultado = importar(repo, [fila(1, "0991112222", "Uno"), fila(2, "593991112222", "Dos")])
    assert (resultado.creados, resultado.actualizados) == (1, 1)
    (contacto,) = repo.contactos.values()
    assert contacto.nombre == "Dos"


def test_repetido_en_lotes_distintos_tampoco_se_duplica() -> None:
    repo = RepoContactosMemoria()
    resultado = importar(
        repo,
        [fila(1, "0991112222", "Uno"), fila(2, "0990000000"), fila(3, "0991112222", "Tres")],
        lote=2,
    )
    assert (resultado.creados, resultado.actualizados) == (2, 1)
    assert len(repo.contactos) == 2


def test_la_unicidad_es_por_dueno() -> None:
    repo = RepoContactosMemoria()
    importar(repo, [fila(1, "0991112222")])
    resultado = importar(repo, [fila(1, "0991112222")], dueno=LUIS)
    assert resultado.creados == 1
    assert len(repo.contactos) == 2


def test_una_fila_con_datos_invalidos_no_deja_el_contacto_a_medias() -> None:
    repo = RepoContactosMemoria()
    importar(repo, [fila(1, "0991112222", "Pedro", etiquetas="vip")])
    resultado = importar(repo, [fila(7, "0991112222", "Nuevo", etiquetas="x" * 300)])
    assert [(r.numero, r.campo) for r in resultado.rechazadas] == [(7, "etiquetas")]
    (contacto,) = repo.contactos.values()
    assert (contacto.nombre, contacto.etiquetas) == ("Pedro", ("vip",))


def test_procesa_por_lotes_sin_consultar_por_fila() -> None:
    repo = RepoContactosMemoria()
    filas = (fila(i, f"5939{i:08d}") for i in range(1, 1001))
    resultado = importar(repo, filas, lote=250)
    assert resultado.creados == 1000
    assert repo.busquedas == 4
    assert repo.guardados_en_bloque == 4


def test_consume_las_filas_de_a_un_lote() -> None:
    """Prueba de memoria: nunca se leen mas filas que las del lote en curso."""
    repo = RepoContactosMemoria()
    leidas = 0
    maximo_adelantado = 0

    def generar() -> Iterator[FilaImportacion]:
        nonlocal leidas, maximo_adelantado
        for i in range(1, 10_001):
            leidas += 1
            maximo_adelantado = max(maximo_adelantado, leidas - len(repo.contactos))
            yield fila(i, f"5939{i:08d}")

    resultado = importar(repo, generar(), lote=500)
    assert resultado.creados == 10_000
    assert maximo_adelantado <= 500


def test_un_lote_sin_filas_validas_no_abre_transaccion() -> None:
    repo = RepoContactosMemoria()
    uow = UnidadDeTrabajoFalsa()
    ImportarContactos(repo, IDS, uow).ejecutar(ANA, [fila(1, "abc")])
    assert uow.confirmaciones == 0
    assert repo.busquedas == 0


def test_el_lote_debe_ser_positivo() -> None:
    with pytest.raises(ValueError):
        ImportarContactos(RepoContactosMemoria(), IDS, UnidadDeTrabajoFalsa(), tamano_lote=0)
