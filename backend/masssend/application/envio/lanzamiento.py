"""Lanzar, cancelar y consultar el progreso de una campana.

Reemplaza a la accion del panel que arrancaba _send_campaign_background en un
hilo del proceso web. Lanzar ya no envia nada: deja un envio pendiente por
destinatario, reserva sus creditos y publica los trabajos en la cola. Si el
servidor se reinicia, los envios siguen en la base y la cola los retoma.
"""

from dataclasses import dataclass

from masssend.application.envio.puertos import (
    ICanalMensajeria,
    IColaEnvios,
    IReservaCreditos,
    ReservaRechazada,
    TrabajoEnvio,
)
from masssend.application.shared.puertos import IGeneradorIds, IUnidadDeTrabajo
from masssend.domain.campanas.campana import EstadoCampana
from masssend.domain.campanas.repositorios import IRepoCampanas, IRepoContactos
from masssend.domain.envio.envio import Envio, Progreso
from masssend.domain.envio.lanzamiento import Lanzamiento
from masssend.domain.envio.politica import PoliticaEnvio
from masssend.domain.envio.repositorios import IRepoEnvios, IRepoLanzamientos
from masssend.domain.shared.errores import (
    EstadoInvalido,
    SaldoInsuficiente,
    ServicioNoDisponible,
)
from masssend.domain.shared.identificadores import IdPublico
from masssend.domain.shared.paginacion import PeticionPagina

PAGINA_DESTINATARIOS = 100
CANAL_DESCONECTADO = "WhatsApp no está conectado. Vincula el número antes de lanzar."


@dataclass(frozen=True, slots=True)
class CampanaLanzada:
    campana_id: IdPublico
    total: int
    duracion_estimada_segundos: int


@dataclass(frozen=True, slots=True)
class CampanaCancelada:
    campana_id: IdPublico
    envios_cancelados: int
    creditos_liberados: int


@dataclass(frozen=True, slots=True)
class EstadoEnvioCampana:
    campana_id: IdPublico
    estado: EstadoCampana
    progreso: Progreso


class LanzarCampana:
    def __init__(
        self,
        campanas: IRepoCampanas,
        contactos: IRepoContactos,
        envios: IRepoEnvios,
        lanzamientos: IRepoLanzamientos,
        reservas: IReservaCreditos,
        canal: ICanalMensajeria,
        cola: IColaEnvios,
        ids: IGeneradorIds,
        uow: IUnidadDeTrabajo,
        politica: PoliticaEnvio | None = None,
    ) -> None:
        self._campanas = campanas
        self._contactos = contactos
        self._envios = envios
        self._lanzamientos = lanzamientos
        self._reservas = reservas
        self._canal = canal
        self._cola = cola
        self._ids = ids
        self._uow = uow
        self._politica = politica or PoliticaEnvio()

    def ejecutar(self, owner_id: IdPublico, campana_id: IdPublico) -> CampanaLanzada:
        # Igual que el sistema actual: sin WhatsApp no se lanza ni se cobra nada.
        if not self._canal.conectado():
            raise ServicioNoDisponible(CANAL_DESCONECTADO)
        with self._uow:
            campana = self._campanas.bloquear(owner_id, campana_id)
            campana.iniciar()
            trabajos = self._crear_envios(owner_id, campana_id, campana.etiquetas)
            if not trabajos:
                raise EstadoInvalido("La campaña no tiene destinatarios.")
            # Se reserva lo que realmente se creo, asi reserva y envios siempre coinciden.
            reserva = self._reservas.reservar(owner_id, campana_id, len(trabajos))
            if isinstance(reserva, ReservaRechazada):
                raise SaldoInsuficiente(
                    "No tienes créditos suficientes para esta campaña.",
                    requerido=reserva.requerido,
                    disponible=reserva.disponible,
                )
            self._lanzamientos.agregar(
                Lanzamiento(campana_id, owner_id, reserva.reserva_id, len(trabajos))
            )
            self._campanas.guardar(campana)
            # La cola solo se entera si todo lo anterior quedo confirmado.
            self._uow.al_confirmar(lambda: self._cola.publicar(trabajos))
        return CampanaLanzada(campana_id, len(trabajos), self._politica.duracion(len(trabajos)))

    def _crear_envios(
        self, owner_id: IdPublico, campana_id: IdPublico, etiquetas: tuple[str, ...]
    ) -> list[TrabajoEnvio]:
        """Recorre los destinatarios por paginas para no cargarlos todos a la vez."""
        trabajos: list[TrabajoEnvio] = []
        peticion = PeticionPagina(limite=PAGINA_DESTINATARIOS)
        while True:
            pagina = self._contactos.destinatarios(owner_id, etiquetas, peticion)
            envios = []
            for contacto in pagina.elementos:
                orden = len(trabajos)
                envio = Envio(
                    self._ids.nuevo(),
                    campana_id,
                    owner_id,
                    contacto.id,
                    contacto.telefono.numero,
                    orden,
                )
                envios.append(envio)
                trabajos.append(TrabajoEnvio(envio.id, self._politica.retraso(orden)))
            self._envios.agregar_varios(envios)
            if pagina.siguiente_cursor is None:
                return trabajos
            peticion = PeticionPagina(limite=PAGINA_DESTINATARIOS, cursor=pagina.siguiente_cursor)


class CancelarCampana:
    """Detiene lo pendiente y devuelve sus creditos. Un borrador tambien se cancela."""

    def __init__(
        self,
        campanas: IRepoCampanas,
        envios: IRepoEnvios,
        lanzamientos: IRepoLanzamientos,
        reservas: IReservaCreditos,
        uow: IUnidadDeTrabajo,
    ) -> None:
        self._campanas = campanas
        self._envios = envios
        self._lanzamientos = lanzamientos
        self._reservas = reservas
        self._uow = uow

    def ejecutar(self, owner_id: IdPublico, campana_id: IdPublico) -> CampanaCancelada:
        with self._uow:
            campana = self._campanas.bloquear(owner_id, campana_id)
            campana.cancelar()
            cancelados = self._envios.cancelar_pendientes(campana_id)
            liberados = 0
            lanzamiento = self._lanzamientos.obtener(campana_id)
            if lanzamiento is not None:
                liberados = self._reservas.liberar(lanzamiento.reserva_id).liberados
            self._campanas.guardar(campana)
        return CampanaCancelada(campana_id, cancelados, liberados)


class ConsultarProgreso:
    def __init__(self, campanas: IRepoCampanas, envios: IRepoEnvios) -> None:
        self._campanas = campanas
        self._envios = envios

    def ejecutar(self, owner_id: IdPublico, campana_id: IdPublico) -> EstadoEnvioCampana:
        campana = self._campanas.obtener(owner_id, campana_id)
        return EstadoEnvioCampana(campana_id, campana.estado, self._envios.progreso(campana_id))
