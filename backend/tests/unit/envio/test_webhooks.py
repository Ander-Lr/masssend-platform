"""Avisos del gateway: BAJA, acuses que solo avanzan y resultados por envio_id."""

from dataclasses import dataclass, field

import pytest

from masssend.application.envio.puertos import IConexionWhatsApp, IHistorialMensajes
from masssend.application.envio.webhooks import (
    EntranteRegistrado,
    MensajeEntrante,
    RecibirMensaje,
    RegistrarAcuse,
    RegistrarResultado,
    ResultadoGateway,
)
from masssend.application.envio.whatsapp import (
    CerrarSesionWhatsApp,
    ConsultarWhatsApp,
    VincularWhatsApp,
)
from masssend.domain.campanas.contacto import Contacto
from masssend.domain.campanas.telefono import Telefono
from masssend.domain.envio.entrega import EstadoEntrega, avanza, es_solicitud_de_baja
from masssend.domain.envio.envio import Envio, EstadoEnvio
from masssend.domain.shared.errores import DatosInvalidos, EstadoInvalido
from masssend.domain.shared.identificadores import IdPublico
from tests.fakes.campanas import RepoContactosMemoria
from tests.fakes.envio import ConexionFalsa, HistorialMensajesMemoria, RepoEnviosMemoria
from tests.fakes.ids import GeneradorIdsSecuencial
from tests.fakes.unidad_de_trabajo import UnidadDeTrabajoFalsa

E = EstadoEntrega


@pytest.mark.parametrize(
    "texto", ["BAJA", "baja", " Baja. ", "¡BAJA!", "bája", "Darme de baja", "STOP"]
)
def test_reconoce_la_baja(texto: str) -> None:
    assert es_solicitud_de_baja(texto)


@pytest.mark.parametrize(
    "texto", ["", "hola", "no me den de baja", "BAJAR precios", "baja por favor gracias"]
)
def test_una_frase_que_solo_contiene_baja_no_cuenta(texto: str) -> None:
    assert not es_solicitud_de_baja(texto)


@pytest.mark.parametrize(
    ("actual", "nuevo", "esperado"),
    [
        (E.PENDIENTE, E.ENVIADO, True),
        (E.ENVIADO, E.ENTREGADO, True),
        (E.ENTREGADO, E.LEIDO, True),
        (E.LEIDO, E.ENTREGADO, False),
        (E.ENTREGADO, E.ENTREGADO, False),
        (E.PENDIENTE, E.FALLIDO, True),
        (E.ENVIADO, E.FALLIDO, False),
        (E.FALLIDO, E.ENVIADO, True),
    ],
)
def test_el_estado_de_entrega_solo_avanza(actual: E, nuevo: E, esperado: bool) -> None:
    assert avanza(actual, nuevo) is esperado


IDS = GeneradorIdsSecuencial()


def envio(estado: EstadoEnvio = EstadoEnvio.ENVIADO) -> Envio:
    return Envio(IDS.nuevo(), IDS.nuevo(), IDS.nuevo(), IDS.nuevo(), "593991112222", 0, estado)


def test_confirmar_guarda_el_id_una_vez() -> None:
    e = envio()
    assert e.confirmar("wamid.1")
    assert not e.confirmar("wamid.2")
    assert e.id_externo == "wamid.1"
    assert not e.confirmar(None)
    assert not envio(EstadoEnvio.PENDIENTE).confirmar("wamid.3")


def test_rebotar_un_envio_que_salio() -> None:
    e = envio()
    assert e.rebotar("Número bloqueado")
    assert (e.estado, e.detalle) == (EstadoEnvio.FALLIDO, "Número bloqueado")
    assert not e.rebotar("otra vez")
    assert not envio(EstadoEnvio.PENDIENTE).rebotar("x")
    rebotado = envio()
    rebotado.rebotar("")
    assert rebotado.detalle == "WhatsApp no entregó el mensaje."


@dataclass
class Entorno:
    ids: GeneradorIdsSecuencial = field(default_factory=GeneradorIdsSecuencial)
    uow: UnidadDeTrabajoFalsa = field(default_factory=UnidadDeTrabajoFalsa)
    contactos: RepoContactosMemoria = field(default_factory=RepoContactosMemoria)
    historial: HistorialMensajesMemoria = field(default_factory=HistorialMensajesMemoria)
    envios: RepoEnviosMemoria = field(default_factory=RepoEnviosMemoria)

    def contacto(self, numero: str, dueno: IdPublico | None = None) -> Contacto:
        contacto = Contacto.nuevo(
            self.ids.nuevo(), dueno or self.ids.nuevo(), Telefono.desde_texto(numero)
        )
        self.contactos.guardar(contacto)
        return contacto

    def recibir(
        self, telefono: str, texto: str, id_externo: str | None = "wa.1"
    ) -> EntranteRegistrado:
        caso = RecibirMensaje(self.contactos, self.historial, self.uow)
        return caso.ejecutar(MensajeEntrante(telefono, texto, id_externo))

    def resultado(self, resultado: ResultadoGateway) -> int:
        return RegistrarResultado(self.envios, self.historial, self.uow).ejecutar(resultado)


def test_los_fakes_cumplen_los_puertos() -> None:
    historial: IHistorialMensajes = HistorialMensajesMemoria()
    conexion: IConexionWhatsApp = ConexionFalsa()
    assert historial and conexion


def test_un_mensaje_normal_solo_se_registra() -> None:
    e = Entorno()
    pedro = e.contacto("0991112222")
    resultado = e.recibir("593991112222", "Hola, ¿tienen envío a Quito?")
    assert (resultado.repetido, resultado.baja) == (False, False)
    assert e.historial.entrantes == [("593991112222", "Hola, ¿tienen envío a Quito?", "wa.1")]
    assert e.contactos.contactos[pedro.id].puede_recibir


def test_baja_da_de_baja_en_todas_las_libretas() -> None:
    e = Entorno()
    de_ana = e.contacto("0991112222")
    de_luis = e.contacto("0991112222")
    otro = e.contacto("0993334444")
    resultado = e.recibir("+593 99 111 2222", "BAJA")
    assert resultado.baja and resultado.contactos_dados_de_baja == 2
    assert not e.contactos.contactos[de_ana.id].puede_recibir
    assert not e.contactos.contactos[de_luis.id].puede_recibir
    assert e.contactos.contactos[otro.id].puede_recibir


def test_un_mensaje_repetido_no_hace_nada() -> None:
    e = Entorno()
    e.contacto("0991112222")
    e.recibir("593991112222", "hola", "wa.7")
    repetido = e.recibir("593991112222", "BAJA", "wa.7")
    assert repetido.repetido and not repetido.baja
    assert len(e.historial.entrantes) == 1


def test_baja_de_un_numero_desconocido_o_fijo() -> None:
    e = Entorno()
    assert e.recibir("593991112222", "BAJA").contactos_dados_de_baja == 0
    fijo = e.recibir("022345678", "BAJA", "wa.2")
    assert fijo.baja and fijo.contactos_dados_de_baja == 0


def test_un_telefono_vacio_no_se_acepta() -> None:
    with pytest.raises(DatosInvalidos):
        Entorno().recibir("abc", "hola")


def test_acuses() -> None:
    e = Entorno()
    e.historial.acuses["wamid.1"] = E.ENVIADO
    acuse = RegistrarAcuse(e.historial, e.uow)
    assert acuse.ejecutar(" wamid.1 ", E.LEIDO) == 1
    assert acuse.ejecutar("wamid.1", E.ENTREGADO) == 0
    assert e.historial.acuses["wamid.1"] is E.LEIDO
    with pytest.raises(DatosInvalidos):
        acuse.ejecutar(" ", E.LEIDO)


def test_el_resultado_llega_por_envio_id_y_es_idempotente() -> None:
    e = Entorno()
    salio = envio()
    e.envios.agregar_varios([salio])
    confirmado = ResultadoGateway(salio.id, "593991112222", True, "wamid.9")
    assert e.resultado(confirmado) == 1
    assert e.resultado(confirmado) == 0
    assert e.envios.envios[salio.id].id_externo == "wamid.9"


def test_un_rebote_marca_el_envio_como_fallido() -> None:
    e = Entorno()
    salio = envio()
    e.envios.agregar_varios([salio])
    rebote = ResultadoGateway(salio.id, "593991112222", False, motivo="bloqueado")
    assert e.resultado(rebote) == 1
    assert e.resultado(rebote) == 0
    assert e.envios.envios[salio.id].estado is EstadoEnvio.FALLIDO


def test_un_envio_desconocido_se_ignora() -> None:
    assert Entorno().resultado(ResultadoGateway(IDS.nuevo(), "593991112222", True)) == 0


def test_sin_envio_id_es_un_mensaje_del_chat() -> None:
    e = Entorno()
    assert e.resultado(ResultadoGateway(None, "0991112222", True, "wamid.1")) == 1
    assert e.historial.resultados_sin_envio == [("593991112222", True)]


def test_conexion_de_whatsapp() -> None:
    conexion = ConexionFalsa()
    assert not ConsultarWhatsApp(conexion).ejecutar().conectado
    assert VincularWhatsApp(conexion).ejecutar("099 111 2222") == "ABCD-1234"
    assert conexion.vinculaciones == ["593991112222"]
    with pytest.raises(DatosInvalidos):
        VincularWhatsApp(conexion).ejecutar("022345678")
    conexion.conectado = True
    with pytest.raises(EstadoInvalido):
        VincularWhatsApp(conexion).ejecutar("0991112222")
    CerrarSesionWhatsApp(conexion).ejecutar()
    assert not conexion.estado().conectado


def test_dar_de_baja_en_el_repositorio_falso_es_idempotente() -> None:
    e = Entorno()
    e.contacto("0991112222")
    telefono = Telefono.desde_texto("0991112222")
    assert e.contactos.dar_de_baja_en_todas_las_libretas(telefono) == 1
    assert e.contactos.dar_de_baja_en_todas_las_libretas(telefono) == 0
