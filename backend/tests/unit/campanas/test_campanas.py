from dataclasses import dataclass, field
from typing import Any

import pytest

from masssend.application.campanas.campanas import (
    CambiosCampana,
    CrearCampana,
    DescargarAdjunto,
    EditarCampana,
    EliminarCampana,
    ListarCampanas,
    ObtenerCampana,
    SubirAdjunto,
)
from masssend.application.campanas.puertos import IAlmacenArchivos
from masssend.domain.campanas.campana import Campana, EstadoCampana
from masssend.domain.campanas.contacto import Contacto
from masssend.domain.campanas.repositorios import FiltroCampanas, IRepoCampanas
from masssend.domain.campanas.telefono import Telefono
from masssend.domain.shared.errores import (
    DatosInvalidos,
    EstadoInvalido,
    RecursoNoEncontrado,
    ServicioNoDisponible,
)
from masssend.domain.shared.identificadores import IdPublico
from masssend.domain.shared.paginacion import PeticionPagina
from tests.fakes.campanas import AlmacenArchivosMemoria, RepoCampanasMemoria, RepoContactosMemoria
from tests.fakes.ids import GeneradorIdsSecuencial
from tests.fakes.unidad_de_trabajo import UnidadDeTrabajoFalsa

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32


@dataclass
class Entorno:
    ids: GeneradorIdsSecuencial = field(default_factory=GeneradorIdsSecuencial)
    uow: UnidadDeTrabajoFalsa = field(default_factory=UnidadDeTrabajoFalsa)
    campanas: RepoCampanasMemoria = field(default_factory=RepoCampanasMemoria)
    contactos: RepoContactosMemoria = field(default_factory=RepoContactosMemoria)
    almacen: AlmacenArchivosMemoria = field(default_factory=AlmacenArchivosMemoria)

    def __post_init__(self) -> None:
        self.ana = self.ids.nuevo()
        self.luis = self.ids.nuevo()

    def contacto(self, numero: str, etiquetas: str = "", baja: bool = False) -> None:
        contacto = Contacto.nuevo(
            self.ids.nuevo(), self.ana, Telefono.desde_texto(numero), etiquetas=etiquetas
        )
        contacto.dado_de_baja = baja
        self.contactos.guardar(contacto)

    def crear(self, etiquetas: str = "", dueno: IdPublico | None = None) -> Campana:
        caso = CrearCampana(self.campanas, self.contactos, self.ids, self.uow)
        return caso.ejecutar(dueno or self.ana, "Promo", "Hola {{nombre}}", etiquetas).campana

    def editar(self, campana_id: IdPublico, **cambios: Any) -> Campana:
        caso = EditarCampana(self.campanas, self.contactos, self.uow)
        return caso.ejecutar(self.ana, campana_id, CambiosCampana(**cambios)).campana

    def subir(
        self, campana_id: IdPublico, nombre: str = "promo.png", contenido: bytes = PNG
    ) -> Campana:
        caso = SubirAdjunto(self.campanas, self.contactos, self.almacen, self.uow)
        return caso.ejecutar(self.ana, campana_id, nombre, contenido).campana

    def estado(self, campana_id: IdPublico, estado: EstadoCampana) -> None:
        campana = self.campanas.obtener(self.ana, campana_id)
        campana.estado = estado
        self.campanas.guardar(campana)


def test_los_fakes_cumplen_los_puertos() -> None:
    repo: IRepoCampanas = RepoCampanasMemoria()
    almacen: IAlmacenArchivos = AlmacenArchivosMemoria()
    assert repo and almacen


def test_crear_guarda_un_borrador_y_cuenta_destinatarios() -> None:
    e = Entorno()
    e.contacto("0991111111", "vip")
    e.contacto("0992222222", "lead")
    e.contacto("0993333333", "vip", baja=True)
    detalle = CrearCampana(e.campanas, e.contactos, e.ids, e.uow).ejecutar(
        e.ana, "Promo", "Hola", "vip"
    )
    assert detalle.campana.estado is EstadoCampana.BORRADOR
    assert detalle.destinatarios == 1
    assert e.campanas.obtener(e.ana, detalle.campana.id).nombre == "Promo"


def test_sin_etiquetas_llega_a_todos_los_que_no_se_dieron_de_baja() -> None:
    e = Entorno()
    e.contacto("0991111111", "vip")
    e.contacto("0992222222")
    e.contacto("0993333333", baja=True)
    campana = e.crear()
    assert ObtenerCampana(e.campanas, e.contactos).ejecutar(e.ana, campana.id).destinatarios == 2


def test_crear_con_datos_invalidos_no_guarda() -> None:
    e = Entorno()
    with pytest.raises(DatosInvalidos):
        CrearCampana(e.campanas, e.contactos, e.ids, e.uow).ejecutar(e.ana, "", "Hola")
    assert e.campanas.campanas == {}


def test_una_campana_ajena_no_existe() -> None:
    e = Entorno()
    campana = e.crear()
    with pytest.raises(RecursoNoEncontrado):
        ObtenerCampana(e.campanas, e.contactos).ejecutar(e.luis, campana.id)
    with pytest.raises(RecursoNoEncontrado):
        EditarCampana(e.campanas, e.contactos, e.uow).ejecutar(
            e.luis, campana.id, CambiosCampana(nombre="Robada")
        )
    with pytest.raises(RecursoNoEncontrado):
        EliminarCampana(e.campanas, e.uow).ejecutar(e.luis, campana.id)
    with pytest.raises(RecursoNoEncontrado):
        SubirAdjunto(e.campanas, e.contactos, e.almacen, e.uow).ejecutar(
            e.luis, campana.id, "promo.png", PNG
        )
    assert e.almacen.archivos == {}


def test_editar_un_borrador_recalcula_destinatarios() -> None:
    e = Entorno()
    e.contacto("0991111111", "vip")
    campana = e.crear("lead")
    caso = EditarCampana(e.campanas, e.contactos, e.uow)
    detalle = caso.ejecutar(e.ana, campana.id, CambiosCampana(etiquetas=["vip"]))
    assert detalle.campana.etiquetas == ("vip",)
    assert detalle.destinatarios == 1
    assert e.campanas.bloqueos == 1


def test_editar_una_campana_en_curso_falla_y_revierte() -> None:
    e = Entorno()
    campana = e.crear()
    e.estado(campana.id, EstadoCampana.EN_CURSO)
    with pytest.raises(EstadoInvalido):
        e.editar(campana.id, nombre="Otra")
    assert e.uow.reversiones == 1
    assert e.campanas.obtener(e.ana, campana.id).nombre == "Promo"


def test_eliminar() -> None:
    e = Entorno()
    campana = e.crear()
    EliminarCampana(e.campanas, e.uow).ejecutar(e.ana, campana.id)
    assert e.campanas.campanas == {}


def test_una_campana_en_curso_no_se_elimina() -> None:
    e = Entorno()
    campana = e.crear()
    e.estado(campana.id, EstadoCampana.EN_CURSO)
    with pytest.raises(EstadoInvalido):
        EliminarCampana(e.campanas, e.uow).ejecutar(e.ana, campana.id)
    assert campana.id in e.campanas.campanas


def test_listar_solo_las_propias_y_por_estado() -> None:
    e = Entorno()
    primera = e.crear()
    segunda = e.crear()
    e.crear(dueno=e.luis)
    e.estado(primera.id, EstadoCampana.COMPLETADA)
    listar = ListarCampanas(e.campanas)
    assert [c.id for c in listar.ejecutar(e.ana).elementos] == [segunda.id, primera.id]
    completadas = listar.ejecutar(e.ana, FiltroCampanas(EstadoCampana.COMPLETADA)).elementos
    assert [c.id for c in completadas] == [primera.id]
    pagina = listar.ejecutar(e.ana, peticion=PeticionPagina(limite=1))
    assert pagina.tiene_mas


def test_subir_y_descargar_adjunto() -> None:
    e = Entorno()
    campana = e.crear()
    actualizada = e.subir(campana.id)
    assert actualizada.adjunto in e.almacen.archivos
    archivo = DescargarAdjunto(e.campanas, e.almacen).ejecutar(e.ana, campana.id)
    assert (archivo.nombre, archivo.tipo, archivo.contenido) == ("promo.png", "image/png", PNG)


def test_un_png_renombrado_no_llega_al_almacen() -> None:
    e = Entorno()
    campana = e.crear()
    with pytest.raises(DatosInvalidos):
        e.subir(campana.id, "video.mp4", PNG)
    assert e.almacen.archivos == {}


def test_no_se_sube_adjunto_a_una_campana_que_no_es_borrador() -> None:
    e = Entorno()
    campana = e.crear()
    e.estado(campana.id, EstadoCampana.COMPLETADA)
    with pytest.raises(EstadoInvalido):
        e.subir(campana.id)
    assert e.almacen.archivos == {}


def test_si_el_almacen_cae_la_campana_queda_igual() -> None:
    e = Entorno()
    campana = e.crear()
    e.almacen.disponible = False
    with pytest.raises(ServicioNoDisponible):
        e.subir(campana.id)
    assert e.campanas.obtener(e.ana, campana.id).adjunto is None


def test_descargar_sin_adjunto_o_ajeno_no_existe() -> None:
    e = Entorno()
    campana = e.crear()
    descargar = DescargarAdjunto(e.campanas, e.almacen)
    with pytest.raises(RecursoNoEncontrado):
        descargar.ejecutar(e.ana, campana.id)
    e.subir(campana.id)
    with pytest.raises(RecursoNoEncontrado):
        descargar.ejecutar(e.luis, campana.id)


def test_un_adjunto_que_ya_no_esta_en_el_almacen_no_existe() -> None:
    e = Entorno()
    campana = e.crear()
    e.subir(campana.id)
    e.almacen.archivos.clear()
    with pytest.raises(RecursoNoEncontrado):
        DescargarAdjunto(e.campanas, e.almacen).ejecutar(e.ana, campana.id)
