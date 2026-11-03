"""Procesar un envio: lo que hace el trabajador por cada trabajo de la cola.

Es idempotente: el envio se bloquea y solo se procesa si sigue pendiente. Si
la cola entrega el mismo trabajo dos veces, la segunda no envia ni cobra.
Cada credito se cobra cuando el mensaje sale, no antes. Al procesar el
ultimo, la campana se completa y se devuelve lo que no se uso.
"""

from dataclasses import dataclass

from masssend.application.envio.puertos import (
    ICanalMensajeria,
    IReservaCreditos,
    SolicitudEnvio,
)
from masssend.application.shared.puertos import IUnidadDeTrabajo
from masssend.domain.campanas.campana import Campana, EstadoCampana
from masssend.domain.campanas.repositorios import IRepoCampanas, IRepoContactos
from masssend.domain.envio.envio import Envio, EstadoEnvio
from masssend.domain.envio.lanzamiento import Lanzamiento
from masssend.domain.envio.repositorios import IRepoEnvios, IRepoLanzamientos
from masssend.domain.shared.errores import (
    EstadoInvalido,
    RecursoNoEncontrado,
    ServicioNoDisponible,
)
from masssend.domain.shared.identificadores import IdPublico

DADO_DE_BAJA = "El contacto pidió no recibir mensajes."
CONTACTO_ELIMINADO = "El contacto ya no existe."
CANAL_CAIDO = "WhatsApp no respondió."


@dataclass(frozen=True, slots=True)
class EnvioProcesado:
    """repetido es True si el trabajo ya se habia procesado antes."""

    envio_id: IdPublico
    estado: EstadoEnvio
    repetido: bool = False


class ProcesarEnvio:
    def __init__(
        self,
        campanas: IRepoCampanas,
        contactos: IRepoContactos,
        envios: IRepoEnvios,
        lanzamientos: IRepoLanzamientos,
        reservas: IReservaCreditos,
        canal: ICanalMensajeria,
        uow: IUnidadDeTrabajo,
    ) -> None:
        self._campanas = campanas
        self._contactos = contactos
        self._envios = envios
        self._lanzamientos = lanzamientos
        self._reservas = reservas
        self._canal = canal
        self._uow = uow

    def ejecutar(self, envio_id: IdPublico) -> EnvioProcesado | None:
        """None si el envio no existe, por ejemplo si su campana se elimino."""
        with self._uow:
            envio = self._envios.bloquear(envio_id)
            if envio is None:
                return None
            if not envio.pendiente:
                return EnvioProcesado(envio.id, envio.estado, repetido=True)
            lanzamiento = self._lanzamientos.obtener(envio.campana_id)
            if lanzamiento is None:
                raise EstadoInvalido("El envío no tiene un lanzamiento asociado.")
            campana = self._campanas.obtener(envio.owner_id, envio.campana_id)
            self._enviar(envio, campana, lanzamiento)
            self._envios.guardar(envio)
            self._cerrar_si_termino(envio, lanzamiento)
            return EnvioProcesado(envio.id, envio.estado)

    def _enviar(self, envio: Envio, campana: Campana, lanzamiento: Lanzamiento) -> None:
        try:
            contacto = self._contactos.obtener(envio.owner_id, envio.contacto_id)
        except RecursoNoEncontrado:
            envio.omitir(CONTACTO_ELIMINADO)
            return
        if not contacto.puede_recibir:
            envio.omitir(DADO_DE_BAJA)
            return
        solicitud = SolicitudEnvio(
            envio.id,
            contacto.telefono.numero,
            campana.mensaje_para(contacto.nombre, contacto.datos),
            campana.adjunto,
        )
        try:
            resultado = self._canal.enviar(solicitud)
        except ServicioNoDisponible:
            envio.marcar_fallido(CANAL_CAIDO)
            return
        if not resultado.aceptado:
            envio.marcar_fallido(resultado.motivo or "El canal rechazó el mensaje.")
            return
        envio.marcar_enviado(resultado.id_externo)
        self._reservas.consumir(lanzamiento.reserva_id, envio.id)

    def _cerrar_si_termino(self, envio: Envio, lanzamiento: Lanzamiento) -> None:
        if not self._envios.progreso(envio.campana_id).terminado:
            return
        # Se bloquea la campana: si dos trabajadores terminan a la vez, solo uno la cierra.
        campana = self._campanas.bloquear(envio.owner_id, envio.campana_id)
        if campana.estado is EstadoCampana.EN_CURSO:
            campana.completar()
            self._campanas.guardar(campana)
        # Devuelve lo que no se cobro: fallidos y omitidos. Repetirlo libera cero.
        self._reservas.liberar(lanzamiento.reserva_id)
