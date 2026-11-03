"""Contenedor del modulo de envio.

CANAL_MENSAJERIA: fake en ci, whatsapp en real.
COLA_ENVIOS: sincrona en ci; con cualquier otro valor los trabajos quedan en
la base y los toma el trabajador tareas_envio.
"""

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from masssend.application.envio.consultas import (
    EliminarMensajes,
    EnviarMensajeChat,
    GenerarReporte,
    ListarConversaciones,
    ListarMensajes,
)
from masssend.application.envio.lanzamiento import (
    CancelarCampana,
    ConsultarProgreso,
    LanzarCampana,
)
from masssend.application.envio.procesamiento import ProcesarEnvio
from masssend.application.envio.puertos import ICanalMensajeria, IColaEnvios, IConexionWhatsApp
from masssend.application.envio.webhooks import RecibirMensaje, RegistrarAcuse, RegistrarResultado
from masssend.application.envio.whatsapp import (
    CerrarSesionWhatsApp,
    ConsultarWhatsApp,
    VincularWhatsApp,
)
from masssend.domain.shared.identificadores import IdPublico
from masssend.infrastructure.adapters.cola.base_datos import ColaBaseDatos
from masssend.infrastructure.adapters.cola.sincrona import ColaSincrona
from masssend.infrastructure.adapters.mensajeria.falso import CanalFalso, ConexionFalsa
from masssend.infrastructure.adapters.mensajeria.whatsapp import CanalWhatsApp, ConexionWhatsApp
from masssend.infrastructure.composition.campanas import contenedor_campanas
from masssend.infrastructure.composition.creditos import contenedor_creditos
from masssend.infrastructure.composition.root import contenedor as raiz
from masssend.infrastructure.persistence.campanas.repositorios import (
    RepoCampanasDjango,
    RepoContactosDjango,
)
from masssend.infrastructure.persistence.envio.consultas import ConsultasMensajesDjango
from masssend.infrastructure.persistence.envio.historial import HistorialMensajesDjango
from masssend.infrastructure.persistence.envio.repositorios import (
    RepoEnviosDjango,
    RepoLanzamientosDjango,
)


class ContenedorEnvio:
    def canal(self) -> ICanalMensajeria:
        if settings.CANAL_MENSAJERIA == "fake":
            return CanalFalso()
        if settings.CANAL_MENSAJERIA == "whatsapp":
            return CanalWhatsApp(contenedor_campanas.almacen())
        raise ImproperlyConfigured(f"CANAL_MENSAJERIA={settings.CANAL_MENSAJERIA} no existe aún.")

    def cola(self) -> IColaEnvios:
        if settings.COLA_ENVIOS == "sincrona":
            return ColaSincrona(lambda envio_id: self.procesar_envio().ejecutar(envio_id))
        return ColaBaseDatos(raiz.reloj())

    def lanzar_campana(self) -> LanzarCampana:
        contactos = RepoContactosDjango()
        return LanzarCampana(
            RepoCampanasDjango(contactos),
            contactos,
            RepoEnviosDjango(),
            RepoLanzamientosDjango(),
            contenedor_creditos.reserva_creditos(),
            self.canal(),
            self.cola(),
            raiz.generador_ids(),
            raiz.unidad_de_trabajo(),
        )

    def procesar_envio(self) -> ProcesarEnvio:
        contactos = RepoContactosDjango()
        return ProcesarEnvio(
            RepoCampanasDjango(contactos),
            contactos,
            RepoEnviosDjango(),
            RepoLanzamientosDjango(),
            contenedor_creditos.reserva_creditos(),
            self.canal(),
            raiz.unidad_de_trabajo(),
        )

    def cancelar_campana(self) -> CancelarCampana:
        return CancelarCampana(
            RepoCampanasDjango(),
            RepoEnviosDjango(),
            RepoLanzamientosDjango(),
            contenedor_creditos.reserva_creditos(),
            raiz.unidad_de_trabajo(),
        )

    def consultar_progreso(self) -> ConsultarProgreso:
        return ConsultarProgreso(RepoCampanasDjango(), RepoEnviosDjango())

    def siguiente_vencido(self) -> IdPublico | None:
        """Para el trabajador: el proximo envio pendiente cuya hora ya llego."""
        return RepoEnviosDjango.siguiente_vencido(raiz.reloj().ahora())

    # Avisos del gateway
    def recibir_mensaje(self) -> RecibirMensaje:
        return RecibirMensaje(
            RepoContactosDjango(), HistorialMensajesDjango(), raiz.unidad_de_trabajo()
        )

    def registrar_acuse(self) -> RegistrarAcuse:
        return RegistrarAcuse(HistorialMensajesDjango(), raiz.unidad_de_trabajo())

    def registrar_resultado(self) -> RegistrarResultado:
        return RegistrarResultado(
            RepoEnviosDjango(), HistorialMensajesDjango(), raiz.unidad_de_trabajo()
        )

    # Conexion del numero
    def conexion(self) -> IConexionWhatsApp:
        if settings.CANAL_MENSAJERIA == "fake":
            return ConexionFalsa()
        return ConexionWhatsApp()

    def consultar_whatsapp(self) -> ConsultarWhatsApp:
        return ConsultarWhatsApp(self.conexion())

    def vincular_whatsapp(self) -> VincularWhatsApp:
        return VincularWhatsApp(self.conexion())

    def cerrar_sesion_whatsapp(self) -> CerrarSesionWhatsApp:
        return CerrarSesionWhatsApp(self.conexion())

    # Mensajes, conversaciones y reportes
    def listar_mensajes(self) -> ListarMensajes:
        return ListarMensajes(ConsultasMensajesDjango())

    def eliminar_mensajes(self) -> EliminarMensajes:
        return EliminarMensajes(ConsultasMensajesDjango(), raiz.unidad_de_trabajo())

    def listar_conversaciones(self) -> ListarConversaciones:
        return ListarConversaciones(ConsultasMensajesDjango())

    def enviar_mensaje_chat(self) -> EnviarMensajeChat:
        return EnviarMensajeChat(HistorialMensajesDjango(), self.canal(), raiz.unidad_de_trabajo())

    def generar_reporte(self) -> GenerarReporte:
        return GenerarReporte(ConsultasMensajesDjango(), raiz.reloj())


contenedor_envio = ContenedorEnvio()
