from dataclasses import dataclass, field
from typing import Any

import pytest

from masssend.application.campanas.contactos import (
    CambiosContacto,
    EditarContacto,
    EliminarContacto,
    EliminarContactos,
    GuardarContacto,
    ListarContactos,
    ListarEtiquetas,
    ObtenerContacto,
)
from masssend.domain.campanas.contacto import Contacto
from masssend.domain.campanas.repositorios import FiltroContactos, IRepoContactos
from masssend.domain.shared.errores import DatosInvalidos, RecursoNoEncontrado
from masssend.domain.shared.identificadores import IdPublico
from masssend.domain.shared.paginacion import PeticionPagina
from tests.fakes.campanas import RepoContactosMemoria
from tests.fakes.ids import GeneradorIdsSecuencial
from tests.fakes.unidad_de_trabajo import UnidadDeTrabajoFalsa


@dataclass
class Entorno:
    ids: GeneradorIdsSecuencial = field(default_factory=GeneradorIdsSecuencial)
    uow: UnidadDeTrabajoFalsa = field(default_factory=UnidadDeTrabajoFalsa)
    contactos: RepoContactosMemoria = field(default_factory=RepoContactosMemoria)

    def __post_init__(self) -> None:
        self.ana = self.ids.nuevo()
        self.luis = self.ids.nuevo()

    def guardar(
        self, telefono: str, nombre: str = "", etiquetas: str = "", dueno: IdPublico | None = None
    ) -> tuple[Contacto, bool]:
        caso = GuardarContacto(self.contactos, self.ids, self.uow)
        resultado = caso.ejecutar(dueno or self.ana, telefono, nombre, etiquetas)
        return resultado.contacto, resultado.creado

    def editar(self, contacto_id: IdPublico, dueno: IdPublico, **cambios: Any) -> Contacto:
        caso = EditarContacto(self.contactos, self.uow)
        return caso.ejecutar(dueno, contacto_id, CambiosContacto(**cambios))


def test_el_fake_cumple_el_repositorio() -> None:
    repo: IRepoContactos = RepoContactosMemoria()
    assert repo


def test_guardar_crea_con_el_numero_normalizado() -> None:
    e = Entorno()
    contacto, creado = e.guardar("099 111-2222", "Pedro", "vip")
    assert creado
    assert contacto.telefono.numero == "593991112222"
    assert e.contactos.obtener(e.ana, contacto.id).nombre == "Pedro"
    assert e.uow.confirmaciones == 1


def test_guardar_el_mismo_numero_actualiza_sin_duplicar() -> None:
    e = Entorno()
    primero, _ = e.guardar("0991112222", "Pedro")
    segundo, creado = e.guardar("+593991112222", "Pedro Pérez", "cliente")
    assert not creado
    assert segundo.id == primero.id
    assert len(e.contactos.contactos) == 1
    assert segundo.etiquetas == ("cliente",)


def test_dos_duenos_pueden_tener_el_mismo_numero() -> None:
    e = Entorno()
    e.guardar("0991112222")
    _, creado = e.guardar("0991112222", dueno=e.luis)
    assert creado
    assert len(e.contactos.contactos) == 2


def test_un_numero_invalido_no_abre_la_transaccion() -> None:
    e = Entorno()
    with pytest.raises(DatosInvalidos):
        e.guardar("022345678")
    assert e.uow.confirmaciones == e.uow.reversiones == 0


def test_un_contacto_ajeno_no_existe_para_el_otro_dueno() -> None:
    e = Entorno()
    contacto, _ = e.guardar("0991112222")
    with pytest.raises(RecursoNoEncontrado):
        ObtenerContacto(e.contactos).ejecutar(e.luis, contacto.id)
    with pytest.raises(RecursoNoEncontrado):
        e.editar(contacto.id, e.luis, nombre="Robado")
    with pytest.raises(RecursoNoEncontrado):
        EliminarContacto(e.contactos, e.uow).ejecutar(e.luis, contacto.id)
    assert e.contactos.obtener(e.ana, contacto.id).nombre == "593991112222"


def test_editar_aplica_solo_lo_indicado() -> None:
    e = Entorno()
    contacto, _ = e.guardar("0991112222", "Pedro", "vip")
    editado = e.editar(contacto.id, e.ana, etiquetas="lead", dado_de_baja=True)
    assert (editado.nombre, editado.etiquetas, editado.dado_de_baja) == ("Pedro", ("lead",), True)
    reactivado = e.editar(contacto.id, e.ana, dado_de_baja=False, datos={"notas": "ok"})
    assert reactivado.puede_recibir
    assert reactivado.datos == {"notas": "ok"}


def test_editar_con_datos_invalidos_revierte() -> None:
    e = Entorno()
    contacto, _ = e.guardar("0991112222", "Pedro")
    with pytest.raises(DatosInvalidos):
        e.editar(contacto.id, e.ana, nombre="x" * 151)
    assert e.uow.reversiones == 1
    assert e.contactos.obtener(e.ana, contacto.id).nombre == "Pedro"


def test_eliminar_borra_solo_el_propio() -> None:
    e = Entorno()
    contacto, _ = e.guardar("0991112222")
    EliminarContacto(e.contactos, e.uow).ejecutar(e.ana, contacto.id)
    with pytest.raises(RecursoNoEncontrado):
        ObtenerContacto(e.contactos).ejecutar(e.ana, contacto.id)


def test_listar_solo_muestra_los_del_dueno_y_filtra() -> None:
    e = Entorno()
    e.guardar("0991111111", "Ana Vip", "vip")
    e.guardar("0992222222", "Beto", "lead")
    e.guardar("0993333333", "Carla", "vip", dueno=e.luis)
    listar = ListarContactos(e.contactos)
    assert len(listar.ejecutar(e.ana).elementos) == 2
    vip = listar.ejecutar(e.ana, FiltroContactos(etiqueta="vip")).elementos
    assert [c.nombre for c in vip] == ["Ana Vip"]
    por_texto = listar.ejecutar(e.ana, FiltroContactos(texto="992222")).elementos
    assert [c.nombre for c in por_texto] == ["Beto"]


def test_listar_pagina_por_cursor() -> None:
    e = Entorno()
    for i in range(5):
        e.guardar(f"099111111{i}")
    listar = ListarContactos(e.contactos)
    primera = listar.ejecutar(e.ana, peticion=PeticionPagina(limite=3))
    assert len(primera.elementos) == 3 and primera.tiene_mas
    segunda = listar.ejecutar(
        e.ana, peticion=PeticionPagina(limite=3, cursor=primera.siguiente_cursor)
    )
    assert len(segunda.elementos) == 2 and not segunda.tiene_mas
    vistos = {c.id for c in primera.elementos + segunda.elementos}
    assert len(vistos) == 5


def test_listar_va_del_mas_nuevo_al_mas_antiguo() -> None:
    e = Entorno()
    primero, _ = e.guardar("0991111111")
    segundo, _ = e.guardar("0992222222")
    ids = [c.id for c in ListarContactos(e.contactos).ejecutar(e.ana).elementos]
    assert ids == [segundo.id, primero.id]


def test_guardar_acepta_etiquetas_en_lista() -> None:
    e = Entorno()
    contacto, _ = e.guardar("0991112222", etiquetas="vip")
    editado = e.editar(contacto.id, e.ana, etiquetas=["lead", " vip "])
    assert editado.etiquetas == ("lead", "vip")


def test_eliminar_varios_solo_borra_los_propios() -> None:
    e = Entorno()
    a, _ = e.guardar("0991111111")
    b, _ = e.guardar("0992222222")
    ajeno, _ = e.guardar("0993333333", dueno=e.luis)
    caso = EliminarContactos(e.contactos, e.uow)
    assert caso.ejecutar(e.ana, [a.id, b.id, ajeno.id, e.ids.nuevo(), a.id]) == 2
    assert list(e.contactos.contactos) == [ajeno.id]


@pytest.mark.parametrize("cantidad", [0, EliminarContactos.MAXIMO + 1])
def test_eliminar_varios_exige_una_cantidad_razonable(cantidad: int) -> None:
    e = Entorno()
    with pytest.raises(DatosInvalidos) as error:
        EliminarContactos(e.contactos, e.uow).ejecutar(
            e.ana, [e.ids.nuevo() for _ in range(cantidad)]
        )
    assert error.value.campo == "ids"


def test_las_etiquetas_son_del_dueno_y_sin_repetir() -> None:
    e = Entorno()
    e.guardar("0991111111", etiquetas="vip, cliente")
    e.guardar("0992222222", etiquetas="vip")
    e.guardar("0993333333", etiquetas="secreta", dueno=e.luis)
    assert ListarEtiquetas(e.contactos).ejecutar(e.ana) == ["cliente", "vip"]
