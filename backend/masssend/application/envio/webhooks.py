"""Lo que el gateway de WhatsApp avisa: mensajes recibidos, acuses y resultados.

Reemplaza a api_webhook, api_message_ack y api_send_result. La diferencia
principal esta en los resultados: antes se adivinaba a que mensaje
correspondian (el pendiente mas antiguo del numero); ahora el envio_id viaja
con cada mensaje y vuelve con su resultado.

Todos son idempotentes: el gateway reintenta, y un aviso repetido no cambia nada.
"""

from dataclasses import dataclass

from masssend.application.envio.puertos import IHistorialMensajes
from masssend.application.shared.puertos import IUnidadDeTrabajo
from masssend.domain.campanas.repositorios import IRepoContactos
from masssend.domain.campanas.telefono import Telefono
from masssend.domain.envio.entrega import EstadoEntrega, es_solicitud_de_baja
from masssend.domain.envio.repositorios import IRepoEnvios
from masssend.domain.shared.errores import DatosInvalidos
from masssend.domain.shared.identificadores import IdPublico


@dataclass(frozen=True, slots=True)
class MensajeEntrante:
    telefono: str
    texto: str
    id_externo: str | None = None


@dataclass(frozen=True, slots=True)
class EntranteRegistrado:
    repetido: bool
    baja: bool = False
    contactos_dados_de_baja: int = 0


@dataclass(frozen=True, slots=True)
class ResultadoGateway:
    """envio_id es None para los mensajes del chat del panel."""

    envio_id: IdPublico | None
    telefono: str
    enviado: bool
    id_externo: str | None = None
    motivo: str | None = None


def _numero(telefono: str) -> str:
    """Normaliza si se puede; un numero raro se guarda tal como vino."""
    try:
        return Telefono.desde_texto(telefono).numero
    except DatosInvalidos:
        return "".join(c for c in telefono if c.isdigit())


class RecibirMensaje:
    def __init__(
        self,
        contactos: IRepoContactos,
        historial: IHistorialMensajes,
        uow: IUnidadDeTrabajo,
    ) -> None:
        self._contactos = contactos
        self._historial = historial
        self._uow = uow

    def ejecutar(self, mensaje: MensajeEntrante) -> EntranteRegistrado:
        numero = _numero(mensaje.telefono)
        if not numero:
            raise DatosInvalidos("El teléfono no es válido.", "telefono")
        with self._uow:
            if not self._historial.registrar_entrante(numero, mensaje.texto, mensaje.id_externo):
                return EntranteRegistrado(repetido=True)
            if not es_solicitud_de_baja(mensaje.texto):
                return EntranteRegistrado(repetido=False)
            try:
                telefono = Telefono(numero)
            except DatosInvalidos:
                return EntranteRegistrado(repetido=False, baja=True)
            cambiados = self._contactos.dar_de_baja_en_todas_las_libretas(telefono)
            return EntranteRegistrado(repetido=False, baja=True, contactos_dados_de_baja=cambiados)


class RegistrarAcuse:
    def __init__(self, historial: IHistorialMensajes, uow: IUnidadDeTrabajo) -> None:
        self._historial = historial
        self._uow = uow

    def ejecutar(self, id_externo: str, estado: EstadoEntrega) -> int:
        if not id_externo.strip():
            raise DatosInvalidos("Falta el identificador del mensaje.", "id_externo")
        with self._uow:
            return self._historial.registrar_acuse(id_externo.strip(), estado)


class RegistrarResultado:
    def __init__(
        self,
        envios: IRepoEnvios,
        historial: IHistorialMensajes,
        uow: IUnidadDeTrabajo,
    ) -> None:
        self._envios = envios
        self._historial = historial
        self._uow = uow

    def ejecutar(self, resultado: ResultadoGateway) -> int:
        with self._uow:
            if resultado.envio_id is None:
                return self._historial.registrar_resultado_sin_envio(
                    _numero(resultado.telefono),
                    resultado.enviado,
                    resultado.id_externo,
                    resultado.motivo,
                )
            # Bloquea: si el trabajador aun no confirma este envio, el aviso espera.
            envio = self._envios.bloquear(resultado.envio_id)
            if envio is None:
                # No es de una campana: puede ser un mensaje del chat v1, que viaja con su id.
                return self._historial.registrar_resultado_de_mensaje(
                    resultado.envio_id,
                    resultado.enviado,
                    resultado.id_externo,
                    resultado.motivo,
                )
            if resultado.enviado:
                cambio = envio.confirmar(resultado.id_externo)
            else:
                cambio = envio.rebotar(resultado.motivo or "WhatsApp no entregó el mensaje.")
            if cambio:
                self._envios.guardar(envio)
            return int(cambio)
