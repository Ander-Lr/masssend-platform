"""Lanzar, procesar y cancelar con fakes: sin base, sin WhatsApp y sin esperas."""

from dataclasses import dataclass, field

import pytest

from masssend.application.envio.lanzamiento import (
    CampanaLanzada,
    CancelarCampana,
    ConsultarProgreso,
    LanzarCampana,
)
from masssend.application.envio.procesamiento import EnvioProcesado, ProcesarEnvio
from masssend.application.envio.puertos import ICanalMensajeria, IColaEnvios, IReservaCreditos
from masssend.domain.campanas.campana import Campana, EstadoCampana
from masssend.domain.campanas.contacto import Contacto
from masssend.domain.campanas.telefono import Telefono
from masssend.domain.envio.envio import EstadoEnvio
from masssend.domain.envio.repositorios import IRepoEnvios, IRepoLanzamientos
from masssend.domain.shared.errores import (
    EstadoInvalido,
    RecursoNoEncontrado,
    SaldoInsuficiente,
    ServicioNoDisponible,
)
from masssend.domain.shared.identificadores import IdPublico
from tests.fakes.campanas import RepoCampanasMemoria, RepoContactosMemoria
from tests.fakes.envio import CanalFalso, ColaMemoria, RepoEnviosMemoria, RepoLanzamientosMemoria
from tests.fakes.ids import GeneradorIdsSecuencial
from tests.fakes.reserva_creditos import ReservaCreditosFalsa
from tests.fakes.unidad_de_trabajo import UnidadDeTrabajoFalsa


@dataclass
class Entorno:
    saldo: int = 10
    ids: GeneradorIdsSecuencial = field(default_factory=GeneradorIdsSecuencial)
    uow: UnidadDeTrabajoFalsa = field(default_factory=UnidadDeTrabajoFalsa)
    campanas: RepoCampanasMemoria = field(default_factory=RepoCampanasMemoria)
    contactos: RepoContactosMemoria = field(default_factory=RepoContactosMemoria)
    envios: RepoEnviosMemoria = field(default_factory=RepoEnviosMemoria)
    lanzamientos: RepoLanzamientosMemoria = field(default_factory=RepoLanzamientosMemoria)
    canal: CanalFalso = field(default_factory=CanalFalso)
    cola: ColaMemoria = field(default_factory=ColaMemoria)

    def __post_init__(self) -> None:
        self.creditos = ReservaCreditosFalsa(saldo=self.saldo)
        self.ana = self.ids.nuevo()
        self.luis = self.ids.nuevo()

    def contacto(
        self, numero: str, nombre: str = "", etiquetas: str = "", **datos: str
    ) -> Contacto:
        contacto = Contacto.nuevo(
            self.ids.nuevo(), self.ana, Telefono.desde_texto(numero), nombre, etiquetas, datos
        )
        self.contactos.guardar(contacto)
        return contacto

    def campana(self, etiquetas: str = "", mensaje: str = "Hola {{nombre}}") -> Campana:
        campana = Campana.nueva(self.ids.nuevo(), self.ana, "Promo", mensaje, etiquetas)
        self.campanas.guardar(campana)
        return campana

    def lanzar(self, campana: Campana, dueno: IdPublico | None = None) -> CampanaLanzada:
        return LanzarCampana(
            self.campanas,
            self.contactos,
            self.envios,
            self.lanzamientos,
            self.creditos,
            self.canal,
            self.cola,
            self.ids,
            self.uow,
        ).ejecutar(dueno or self.ana, campana.id)

    def procesar(self, envio_id: IdPublico) -> EnvioProcesado | None:
        return ProcesarEnvio(
            self.campanas,
            self.contactos,
            self.envios,
            self.lanzamientos,
            self.creditos,
            self.canal,
            self.uow,
        ).ejecutar(envio_id)

    def procesar_cola(self) -> list[EnvioProcesado | None]:
        return [self.procesar(t.envio_id) for t in self.cola.trabajos]

    def cancelar(self, campana: Campana) -> tuple[int, int]:
        resultado = CancelarCampana(
            self.campanas, self.envios, self.lanzamientos, self.creditos, self.uow
        ).ejecutar(self.ana, campana.id)
        return resultado.envios_cancelados, resultado.creditos_liberados

    def estado(self, campana: Campana) -> EstadoCampana:
        return self.campanas.obtener(self.ana, campana.id).estado

    def creditos_ana(self) -> tuple[int, int]:
        return self.creditos.saldo(self.ana), self.creditos.reservado(self.ana)


def test_los_fakes_cumplen_los_puertos() -> None:
    envios: IRepoEnvios = RepoEnviosMemoria()
    lanzamientos: IRepoLanzamientos = RepoLanzamientosMemoria()
    canal: ICanalMensajeria = CanalFalso()
    cola: IColaEnvios = ColaMemoria()
    reservas: IReservaCreditos = ReservaCreditosFalsa()
    assert envios and lanzamientos and canal and cola and reservas


def test_lanzar_reserva_crea_los_envios_y_publica_con_el_ritmo() -> None:
    e = Entorno()
    for i in range(3):
        e.contacto(f"099111111{i}", etiquetas="vip")
    e.contacto("0992222222", etiquetas="lead")
    campana = e.campana(etiquetas="vip")
    lanzada = e.lanzar(campana)
    assert (lanzada.total, lanzada.duracion_estimada_segundos) == (3, 6)
    assert e.estado(campana) is EstadoCampana.EN_CURSO
    assert e.creditos_ana() == (10, 3)
    assert [t.retraso_segundos for t in e.cola.trabajos] == [0, 3, 6]
    assert all(envio.pendiente for envio in e.envios.de(campana.id))
    assert e.canal.enviados == []


def test_la_cola_solo_se_entera_si_se_confirma() -> None:
    e = Entorno(saldo=1)
    e.contacto("0991111111")
    e.contacto("0992222222")
    campana = e.campana()
    with pytest.raises(SaldoInsuficiente) as error:
        e.lanzar(campana)
    assert (error.value.requerido, error.value.disponible) == (2, 1)
    assert e.cola.trabajos == []
    assert e.uow.reversiones == 1
    assert e.estado(campana) is EstadoCampana.BORRADOR
    assert e.creditos_ana() == (1, 0)


def test_sin_whatsapp_no_se_lanza_ni_se_cobra() -> None:
    e = Entorno()
    e.contacto("0991111111")
    campana = e.campana()
    e.canal.conectado_ = False
    with pytest.raises(ServicioNoDisponible):
        e.lanzar(campana)
    assert e.creditos_ana() == (10, 0)
    assert e.estado(campana) is EstadoCampana.BORRADOR


def test_sin_destinatarios_no_se_lanza() -> None:
    e = Entorno()
    e.contacto("0991111111", etiquetas="lead")
    campana = e.campana(etiquetas="vip")
    with pytest.raises(EstadoInvalido):
        e.lanzar(campana)
    assert e.creditos_ana() == (10, 0)


def test_solo_se_lanza_un_borrador_propio() -> None:
    e = Entorno()
    e.contacto("0991111111")
    campana = e.campana()
    with pytest.raises(RecursoNoEncontrado):
        e.lanzar(campana, dueno=e.luis)
    e.lanzar(campana)
    with pytest.raises(EstadoInvalido):
        e.lanzar(campana)
    assert e.creditos_ana() == (10, 1)


def test_muchos_destinatarios_se_recorren_por_paginas() -> None:
    e = Entorno(saldo=300)
    for i in range(250):
        e.contacto(f"5939{i:08d}")
    lanzada = e.lanzar(e.campana())
    assert lanzada.total == 250
    assert e.envios.inserciones == 3
    assert e.cola.trabajos[50].retraso_segundos == 270


def test_procesar_toda_la_cola_completa_la_campana() -> None:
    e = Entorno()
    e.contacto("0991111111", "Pedro", ciudad="Quito")
    e.contacto("0992222222")
    campana = e.campana(mensaje="Hola {{nombre}} de {{ciudad}}")
    campana.adjuntar("memoria://promo.png")
    e.campanas.guardar(campana)
    e.lanzar(campana)
    resultados = e.procesar_cola()
    assert all(r is not None and r.estado is EstadoEnvio.ENVIADO for r in resultados)
    textos = sorted(s.texto for s in e.canal.enviados)
    assert textos == ["Hola 593992222222 de {{ciudad}}", "Hola Pedro de Quito"]
    assert {s.adjunto for s in e.canal.enviados} == {"memoria://promo.png"}
    assert e.estado(campana) is EstadoCampana.COMPLETADA
    assert e.creditos_ana() == (8, 0)
    assert all(envio.id_externo for envio in e.envios.de(campana.id))


def test_el_mismo_trabajo_dos_veces_envia_y_cobra_una_sola_vez() -> None:
    e = Entorno()
    e.contacto("0991111111")
    e.contacto("0992222222")
    campana = e.campana()
    e.lanzar(campana)
    primero = e.cola.trabajos[0].envio_id
    e.procesar(primero)
    repetido = e.procesar(primero)
    assert repetido == EnvioProcesado(primero, EstadoEnvio.ENVIADO, repetido=True)
    assert len(e.canal.enviados) == 1
    assert e.creditos_ana() == (9, 1)


def test_quien_se_dio_de_baja_despues_de_lanzar_no_recibe_ni_se_cobra() -> None:
    e = Entorno()
    pedro = e.contacto("0991111111")
    e.contacto("0992222222")
    campana = e.campana()
    e.lanzar(campana)
    pedro.dar_de_baja()
    e.contactos.guardar(pedro)
    e.procesar_cola()
    estados = {envio.telefono: envio.estado for envio in e.envios.de(campana.id)}
    assert estados == {"593991111111": EstadoEnvio.OMITIDO, "593992222222": EstadoEnvio.ENVIADO}
    # Al terminar se devuelve el credito que no se uso.
    assert e.creditos_ana() == (9, 0)
    assert e.estado(campana) is EstadoCampana.COMPLETADA


def test_un_contacto_eliminado_se_omite() -> None:
    e = Entorno()
    pedro = e.contacto("0991111111")
    campana = e.campana()
    e.lanzar(campana)
    e.contactos.eliminar(e.ana, pedro.id)
    (resultado,) = e.procesar_cola()
    assert resultado is not None and resultado.estado is EstadoEnvio.OMITIDO
    assert e.creditos_ana() == (10, 0)


def test_un_numero_rechazado_o_un_canal_caido_fallan_sin_cobrar() -> None:
    e = Entorno()
    e.contacto("0991111111")
    e.contacto("0992222222")
    campana = e.campana()
    e.lanzar(campana)
    rechazado, caido = e.cola.trabajos
    e.canal.rechazados.add(e.envios.envios[rechazado.envio_id].telefono)
    e.procesar(rechazado.envio_id)
    e.canal.caido = True
    e.procesar(caido.envio_id)
    assert all(envio.estado is EstadoEnvio.FALLIDO for envio in e.envios.de(campana.id))
    assert e.envios.envios[rechazado.envio_id].detalle == "El número no tiene WhatsApp."
    assert e.envios.envios[caido.envio_id].detalle == "WhatsApp no respondió."
    assert e.creditos_ana() == (10, 0)
    assert e.estado(campana) is EstadoCampana.COMPLETADA


def test_cancelar_a_la_mitad_detiene_lo_pendiente_y_libera_creditos() -> None:
    e = Entorno()
    for i in range(3):
        e.contacto(f"099111111{i}")
    campana = e.campana()
    e.lanzar(campana)
    e.procesar(e.cola.trabajos[0].envio_id)
    assert e.cancelar(campana) == (2, 2)
    assert e.estado(campana) is EstadoCampana.CANCELADA
    assert e.creditos_ana() == (9, 0)
    # Los trabajos que la cola ya tenia programados no envian nada.
    resultados = [e.procesar(t.envio_id) for t in e.cola.trabajos[1:]]
    assert all(r is not None and r.repetido for r in resultados)
    assert len(e.canal.enviados) == 1


def test_cancelar_un_borrador_no_libera_nada() -> None:
    e = Entorno()
    campana = e.campana()
    assert e.cancelar(campana) == (0, 0)
    assert e.estado(campana) is EstadoCampana.CANCELADA


def test_una_campana_terminada_no_se_cancela() -> None:
    e = Entorno()
    e.contacto("0991111111")
    campana = e.campana()
    e.lanzar(campana)
    e.procesar_cola()
    with pytest.raises(EstadoInvalido):
        e.cancelar(campana)


def test_progreso() -> None:
    e = Entorno()
    for i in range(4):
        e.contacto(f"099111111{i}")
    campana = e.campana()
    consultar = ConsultarProgreso(e.campanas, e.envios)
    assert consultar.ejecutar(e.ana, campana.id).progreso.total == 0
    e.lanzar(campana)
    e.procesar(e.cola.trabajos[0].envio_id)
    estado = consultar.ejecutar(e.ana, campana.id)
    assert estado.estado is EstadoCampana.EN_CURSO
    assert (estado.progreso.enviados, estado.progreso.pendientes) == (1, 3)
    assert estado.progreso.porcentaje == 25
    with pytest.raises(RecursoNoEncontrado):
        consultar.ejecutar(e.luis, campana.id)


def test_un_envio_inexistente_se_ignora() -> None:
    assert Entorno().procesar(GeneradorIdsSecuencial().nuevo()) is None


def test_un_envio_sin_lanzamiento_es_un_error() -> None:
    e = Entorno()
    e.contacto("0991111111")
    campana = e.campana()
    e.lanzar(campana)
    e.lanzamientos.lanzamientos.clear()
    with pytest.raises(EstadoInvalido):
        e.procesar(e.cola.trabajos[0].envio_id)
