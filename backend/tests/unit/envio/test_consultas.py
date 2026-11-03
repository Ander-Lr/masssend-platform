"""Mensajes, chat del panel y reportes con fakes."""

from datetime import UTC, date, datetime

import pytest

from masssend.application.envio.consultas import (
    MAX_ELIMINAR,
    EliminarMensajes,
    EnviarMensajeChat,
    FiltroMensajes,
    GenerarReporte,
    IConsultasMensajes,
    ListarConversaciones,
    ListarMensajes,
    Periodo,
    Reporte,
)
from masssend.application.envio.webhooks import RegistrarResultado, ResultadoGateway
from masssend.domain.envio.entrega import EstadoEntrega
from masssend.domain.shared.errores import DatosInvalidos, ServicioNoDisponible
from tests.fakes.envio import (
    CanalFalso,
    CanalSinConfirmar,
    ConsultasMensajesMemoria,
    HistorialMensajesMemoria,
    RepoEnviosMemoria,
)
from tests.fakes.ids import GeneradorIdsSecuencial
from tests.fakes.reloj import RelojFijo
from tests.fakes.unidad_de_trabajo import UnidadDeTrabajoFalsa

IDS = GeneradorIdsSecuencial()
STAFF = IDS.nuevo()


def test_el_fake_cumple_el_puerto() -> None:
    consultas: IConsultasMensajes = ConsultasMensajesMemoria()
    assert consultas


def test_el_filtro_por_telefono_se_normaliza() -> None:
    consultas = ConsultasMensajesMemoria()
    listar = ListarMensajes(consultas)
    listar.ejecutar(STAFF, FiltroMensajes(telefono="099 111 2222", texto="hola"))
    listar.ejecutar(STAFF, FiltroMensajes(telefono="+57 1"))
    listar.ejecutar(STAFF)
    assert [f.telefono for f in consultas.filtros] == ["593991112222", "571", None]
    assert consultas.filtros[0].texto == "hola"
    assert ListarConversaciones(consultas).ejecutar().elementos == ()


@pytest.mark.parametrize("cantidad", [0, MAX_ELIMINAR + 1])
def test_eliminar_exige_una_cantidad_razonable(cantidad: int) -> None:
    caso = EliminarMensajes(ConsultasMensajesMemoria(), UnidadDeTrabajoFalsa())
    with pytest.raises(DatosInvalidos) as error:
        caso.ejecutar(STAFF, [IDS.nuevo() for _ in range(cantidad)])
    assert error.value.campo == "ids"


def test_eliminar_sin_repetidos() -> None:
    consultas = ConsultasMensajesMemoria()
    uno = IDS.nuevo()
    assert EliminarMensajes(consultas, UnidadDeTrabajoFalsa()).ejecutar(STAFF, [uno, uno]) == 1


def chat(canal: CanalFalso | None = None) -> tuple[EnviarMensajeChat, HistorialMensajesMemoria]:
    historial = HistorialMensajesMemoria()
    return EnviarMensajeChat(historial, canal or CanalFalso(), UnidadDeTrabajoFalsa()), historial


def test_el_chat_registra_y_envia_con_el_id_del_mensaje() -> None:
    canal = CanalFalso()
    caso, historial = chat(canal)
    enviado = caso.ejecutar(STAFF, "099 111 2222", "  Hola Pedro ")
    assert enviado.estado is EstadoEntrega.ENVIADO
    assert canal.enviados[0].envio_id == enviado.id
    assert historial.salientes[enviado.id][:4] == [
        STAFF,
        "593991112222",
        "Hola Pedro",
        EstadoEntrega.ENVIADO,
    ]


def test_con_whatsapp_real_queda_pendiente_hasta_el_webhook() -> None:
    caso, historial = chat(CanalSinConfirmar())
    mensaje = caso.ejecutar(STAFF, "0991112222", "Hola")
    assert mensaje.estado is EstadoEntrega.PENDIENTE
    # El resultado vuelve con el id del mensaje y lo cierra; repetirlo no cambia nada.
    resultado = RegistrarResultado(RepoEnviosMemoria(), historial, UnidadDeTrabajoFalsa())
    aviso = ResultadoGateway(mensaje.id, "593991112222", True, "wamid.1")
    assert resultado.ejecutar(aviso) == 1
    assert resultado.ejecutar(aviso) == 0
    assert historial.salientes[mensaje.id][3:] == [EstadoEntrega.ENVIADO, "wamid.1"]


def test_un_numero_rechazado_queda_fallido() -> None:
    canal = CanalFalso()
    canal.rechazados.add("593991112222")
    caso, historial = chat(canal)
    mensaje = caso.ejecutar(STAFF, "0991112222", "Hola")
    assert (mensaje.estado, mensaje.detalle) == (
        EstadoEntrega.FALLIDO,
        "El número no tiene WhatsApp.",
    )
    assert historial.salientes[mensaje.id][3] is EstadoEntrega.FALLIDO


def test_si_whatsapp_no_responde_queda_fallido_y_se_informa() -> None:
    canal = CanalFalso()
    canal.caido = True
    caso, historial = chat(canal)
    with pytest.raises(ServicioNoDisponible):
        caso.ejecutar(STAFF, "0991112222", "Hola")
    (mensaje,) = historial.salientes.values()
    assert mensaje[3] is EstadoEntrega.FALLIDO


@pytest.mark.parametrize(
    ("telefono", "texto", "campo"),
    [
        ("0991112222", "   ", "texto"),
        ("0991112222", "x" * 4097, "texto"),
        ("022345678", "Hola", "telefono"),
    ],
)
def test_el_chat_valida(telefono: str, texto: str, campo: str) -> None:
    caso, historial = chat()
    with pytest.raises(DatosInvalidos) as error:
        caso.ejecutar(STAFF, telefono, texto)
    assert error.value.campo == campo
    assert historial.salientes == {}


def test_el_reporte_por_defecto_cubre_los_ultimos_30_dias() -> None:
    consultas = ConsultasMensajesMemoria()
    reloj = RelojFijo(datetime(2026, 11, 3, 15, tzinfo=UTC))
    GenerarReporte(consultas, reloj).ejecutar(STAFF)
    GenerarReporte(consultas, reloj).ejecutar(STAFF, hasta=date(2026, 6, 30))
    assert consultas.periodos == [
        Periodo(date(2026, 10, 4), date(2026, 11, 3)),
        Periodo(date(2026, 5, 31), date(2026, 6, 30)),
    ]


@pytest.mark.parametrize(
    ("desde", "hasta"),
    [(date(2026, 2, 1), date(2026, 1, 1)), (date(2024, 12, 1), date(2026, 1, 1))],
)
def test_el_periodo_se_valida(desde: date, hasta: date) -> None:
    with pytest.raises(DatosInvalidos) as error:
        Periodo(desde, hasta)
    assert error.value.campo == "desde"


def test_tasas_del_reporte() -> None:
    periodo = Periodo(date(2026, 1, 1), date(2026, 1, 31))
    reporte = Reporte(periodo, enviados=12, entregados=5, leidos=3, fallidos=1, pendientes=1)
    assert (reporte.tasa_entrega, reporte.tasa_lectura) == (80.0, 30.0)
    assert Reporte(periodo).tasa_entrega == 0.0
