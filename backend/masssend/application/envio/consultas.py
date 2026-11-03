"""Mensajes, conversaciones, chat del panel y reportes.

Las lecturas van directo a DTO por un puerto de consultas, sin pasar por
entidades: asi cada listado cuesta pocas consultas a la base, sin importar
cuantas filas traiga. Reemplaza a api_mensajes_list, api_leer_mensajes,
api_enviar_whatsapp y api_reportes de mass_sender/views.py.
"""

from collections.abc import Collection
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import StrEnum
from typing import Protocol

from masssend.application.envio.puertos import (
    ICanalMensajeria,
    IHistorialMensajes,
    SolicitudEnvio,
)
from masssend.application.shared.puertos import IReloj, IUnidadDeTrabajo
from masssend.domain.campanas.telefono import Telefono
from masssend.domain.envio.entrega import EstadoEntrega
from masssend.domain.shared.errores import DatosInvalidos, ServicioNoDisponible
from masssend.domain.shared.identificadores import IdPublico
from masssend.domain.shared.paginacion import Pagina, PeticionPagina

MAX_TEXTO = 4096
MAX_ELIMINAR = 500
DIAS_POR_DEFECTO = 30
MAX_DIAS_REPORTE = 366


class Direccion(StrEnum):
    ENTRANTE = "entrante"
    SALIENTE = "saliente"


@dataclass(frozen=True, slots=True)
class MensajeVista:
    id: IdPublico
    telefono: str
    nombre: str
    texto: str
    direccion: Direccion
    estado: EstadoEntrega
    fecha: datetime
    campana_id: IdPublico | None = None
    campana: str | None = None


@dataclass(frozen=True, slots=True)
class FiltroMensajes:
    texto: str | None = None
    direccion: Direccion | None = None
    estado: EstadoEntrega | None = None
    telefono: str | None = None


@dataclass(frozen=True, slots=True)
class ConversacionVista:
    telefono: str
    nombre: str
    ultimo_texto: str
    ultima_direccion: Direccion
    ultima_fecha: datetime
    mensajes: int


@dataclass(frozen=True, slots=True)
class Periodo:
    desde: date
    hasta: date

    def __post_init__(self) -> None:
        if self.desde > self.hasta:
            raise DatosInvalidos("La fecha desde no puede ser posterior a hasta.", "desde")
        if (self.hasta - self.desde).days >= MAX_DIAS_REPORTE:
            raise DatosInvalidos(f"El periodo no puede superar {MAX_DIAS_REPORTE} días.", "desde")


@dataclass(frozen=True, slots=True)
class DiaReporte:
    dia: date
    enviados: int
    recibidos: int


@dataclass(frozen=True, slots=True)
class Reporte:
    periodo: Periodo
    enviados: int = 0
    recibidos: int = 0
    entregados: int = 0
    leidos: int = 0
    fallidos: int = 0
    pendientes: int = 0
    por_dia: tuple[DiaReporte, ...] = ()
    campanas: dict[str, int] = field(default_factory=dict)
    contactos: int = 0
    contactos_de_baja: int = 0

    def _tasa(self, cantidad: int) -> float:
        exitosos = self.enviados - self.fallidos - self.pendientes
        return round(cantidad * 100 / exitosos, 1) if exitosos > 0 else 0.0

    @property
    def tasa_entrega(self) -> float:
        """Entregados o leidos sobre los que salieron. Un leido tambien se entrego."""
        return self._tasa(self.entregados + self.leidos)

    @property
    def tasa_lectura(self) -> float:
        return self._tasa(self.leidos)


class IConsultasMensajes(Protocol):
    def mensajes(
        self, owner_id: IdPublico, filtro: FiltroMensajes, peticion: PeticionPagina
    ) -> Pagina[MensajeVista]:
        """Del mas nuevo al mas antiguo. Como maximo tres consultas."""
        ...

    def eliminar_mensajes(self, owner_id: IdPublico, ids: Collection[IdPublico]) -> int:
        """Solo los propios; el resto se ignora."""
        ...

    def conversaciones(self, peticion: PeticionPagina) -> Pagina[ConversacionVista]:
        """Todas las conversaciones, la mas reciente primero. Como maximo tres consultas."""
        ...

    def reporte(self, owner_id: IdPublico, periodo: Periodo) -> Reporte: ...


class ListarMensajes:
    def __init__(self, consultas: IConsultasMensajes) -> None:
        self._consultas = consultas

    def ejecutar(
        self,
        owner_id: IdPublico,
        filtro: FiltroMensajes | None = None,
        peticion: PeticionPagina | None = None,
    ) -> Pagina[MensajeVista]:
        filtro = filtro or FiltroMensajes()
        if filtro.telefono:
            filtro = FiltroMensajes(
                filtro.texto, filtro.direccion, filtro.estado, _numero(filtro.telefono)
            )
        return self._consultas.mensajes(owner_id, filtro, peticion or PeticionPagina())


class EliminarMensajes:
    def __init__(self, consultas: IConsultasMensajes, uow: IUnidadDeTrabajo) -> None:
        self._consultas = consultas
        self._uow = uow

    def ejecutar(self, owner_id: IdPublico, ids: Collection[IdPublico]) -> int:
        unicos = set(ids)
        if not unicos:
            raise DatosInvalidos("Indica al menos un mensaje.", "ids")
        if len(unicos) > MAX_ELIMINAR:
            raise DatosInvalidos(f"Máximo {MAX_ELIMINAR} mensajes por petición.", "ids")
        with self._uow:
            return self._consultas.eliminar_mensajes(owner_id, unicos)


class ListarConversaciones:
    def __init__(self, consultas: IConsultasMensajes) -> None:
        self._consultas = consultas

    def ejecutar(self, peticion: PeticionPagina | None = None) -> Pagina[ConversacionVista]:
        return self._consultas.conversaciones(peticion or PeticionPagina())


@dataclass(frozen=True, slots=True)
class MensajeChat:
    id: IdPublico
    telefono: str
    estado: EstadoEntrega
    detalle: str | None = None


class EnviarMensajeChat:
    """Chat del panel: un mensaje suelto a un numero, sin campana ni creditos.

    El mensaje se guarda como pendiente antes de llamar a WhatsApp, y su id viaja
    al gateway: el resultado vuelve por el webhook con ese mismo id.
    """

    def __init__(
        self,
        historial: IHistorialMensajes,
        canal: ICanalMensajeria,
        uow: IUnidadDeTrabajo,
    ) -> None:
        self._historial = historial
        self._canal = canal
        self._uow = uow

    def ejecutar(self, owner_id: IdPublico, telefono: str, texto: str) -> MensajeChat:
        numero = Telefono.desde_texto(telefono).numero
        limpio = texto.strip()
        if not limpio:
            raise DatosInvalidos("El mensaje está vacío.", "texto")
        if len(limpio) > MAX_TEXTO:
            raise DatosInvalidos(f"El mensaje no puede superar {MAX_TEXTO} caracteres.", "texto")
        with self._uow:
            mensaje_id = self._historial.registrar_saliente(owner_id, numero, limpio)
        try:
            resultado = self._canal.enviar(SolicitudEnvio(mensaje_id, numero, limpio))
        except ServicioNoDisponible as error:
            self._cerrar(mensaje_id, False, None, error.mensaje)
            raise
        if not resultado.aceptado:
            motivo = resultado.motivo or "WhatsApp rechazó el mensaje."
            self._cerrar(mensaje_id, False, None, motivo)
            return MensajeChat(mensaje_id, numero, EstadoEntrega.FALLIDO, motivo)
        if resultado.id_externo:
            # El canal ya lo confirmo; con WhatsApp real queda pendiente hasta el webhook.
            self._cerrar(mensaje_id, True, resultado.id_externo, None)
            return MensajeChat(mensaje_id, numero, EstadoEntrega.ENVIADO)
        return MensajeChat(mensaje_id, numero, EstadoEntrega.PENDIENTE)

    def _cerrar(
        self, mensaje_id: IdPublico, enviado: bool, id_externo: str | None, motivo: str | None
    ) -> None:
        with self._uow:
            self._historial.registrar_resultado_de_mensaje(mensaje_id, enviado, id_externo, motivo)


class GenerarReporte:
    def __init__(self, consultas: IConsultasMensajes, reloj: IReloj) -> None:
        self._consultas = consultas
        self._reloj = reloj

    def ejecutar(
        self, owner_id: IdPublico, desde: date | None = None, hasta: date | None = None
    ) -> Reporte:
        """Sin fechas, los ultimos 30 dias, como el sistema actual."""
        hasta = hasta or self._reloj.ahora().date()
        desde = desde or hasta - timedelta(days=DIAS_POR_DEFECTO)
        return self._consultas.reporte(owner_id, Periodo(desde, hasta))


def _numero(telefono: str) -> str:
    try:
        return Telefono.desde_texto(telefono).numero
    except DatosInvalidos:
        return "".join(c for c in telefono if c.isdigit())
