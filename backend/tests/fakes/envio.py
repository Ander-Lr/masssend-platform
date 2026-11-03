from collections import Counter
from collections.abc import Sequence
from dataclasses import replace

from masssend.application.envio.puertos import ResultadoCanal, SolicitudEnvio, TrabajoEnvio
from masssend.domain.envio.envio import Envio, EstadoEnvio, Progreso
from masssend.domain.envio.lanzamiento import Lanzamiento
from masssend.domain.shared.errores import ServicioNoDisponible
from masssend.domain.shared.identificadores import IdPublico


class RepoEnviosMemoria:
    def __init__(self) -> None:
        self.envios: dict[IdPublico, Envio] = {}
        self.inserciones = 0

    def agregar_varios(self, envios: Sequence[Envio]) -> None:
        self.inserciones += 1
        for envio in envios:
            self.envios[envio.id] = replace(envio)

    def bloquear(self, envio_id: IdPublico) -> Envio | None:
        envio = self.envios.get(envio_id)
        return replace(envio) if envio else None

    def guardar(self, envio: Envio) -> None:
        self.envios[envio.id] = replace(envio)

    def cancelar_pendientes(self, campana_id: IdPublico) -> int:
        pendientes = [e for e in self.de(campana_id) if e.pendiente]
        for envio in pendientes:
            envio.cancelar()
        return len(pendientes)

    def progreso(self, campana_id: IdPublico) -> Progreso:
        conteo = Counter(e.estado for e in self.de(campana_id))
        return Progreso(
            total=sum(conteo.values()),
            enviados=conteo[EstadoEnvio.ENVIADO],
            fallidos=conteo[EstadoEnvio.FALLIDO],
            omitidos=conteo[EstadoEnvio.OMITIDO],
            cancelados=conteo[EstadoEnvio.CANCELADO],
        )

    def de(self, campana_id: IdPublico) -> list[Envio]:
        """Para las pruebas: los envios de una campana en orden de salida."""
        return sorted(
            (e for e in self.envios.values() if e.campana_id == campana_id), key=lambda e: e.orden
        )


class RepoLanzamientosMemoria:
    def __init__(self) -> None:
        self.lanzamientos: dict[IdPublico, Lanzamiento] = {}

    def agregar(self, lanzamiento: Lanzamiento) -> None:
        self.lanzamientos[lanzamiento.campana_id] = lanzamiento

    def obtener(self, campana_id: IdPublico) -> Lanzamiento | None:
        return self.lanzamientos.get(campana_id)


class CanalFalso:
    """Registra lo que envia. Puede simular desconexion, caida o numeros rechazados."""

    def __init__(self) -> None:
        self.enviados: list[SolicitudEnvio] = []
        self.conectado_ = True
        self.caido = False
        self.rechazados: set[str] = set()

    def conectado(self) -> bool:
        return self.conectado_

    def enviar(self, solicitud: SolicitudEnvio) -> ResultadoCanal:
        if self.caido:
            raise ServicioNoDisponible("El canal no responde.")
        if solicitud.telefono in self.rechazados:
            return ResultadoCanal(False, motivo="El número no tiene WhatsApp.")
        self.enviados.append(solicitud)
        return ResultadoCanal(True, id_externo=f"wamid.{len(self.enviados)}")


class ColaMemoria:
    """Guarda los trabajos publicados; la prueba decide cuando procesarlos."""

    def __init__(self) -> None:
        self.trabajos: list[TrabajoEnvio] = []

    def publicar(self, trabajos: Sequence[TrabajoEnvio]) -> None:
        self.trabajos.extend(trabajos)
