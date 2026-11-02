"""Notificaciones por correo y control de su cola."""

from masssend.application.identidad.puertos import IColaNotificaciones, TareaCorreo
from masssend.application.shared.puertos import IGeneradorIds
from masssend.domain.identidad.notificacion import Notificacion
from masssend.domain.shared.identificadores import IdPublico
from masssend.domain.shared.paginacion import Pagina, PeticionPagina


class EnviarNotificacion:
    def __init__(self, cola: IColaNotificaciones, ids: IGeneradorIds) -> None:
        self._cola = cola
        self._ids = ids

    def ejecutar(self, notificacion: Notificacion) -> IdPublico:
        tarea_id = self._ids.nuevo()
        self._cola.encolar(notificacion, tarea_id)
        return tarea_id


class ConsultarCola:
    def __init__(self, cola: IColaNotificaciones) -> None:
        self._cola = cola

    def ejecutar(self, peticion: PeticionPagina) -> tuple[Pagina[TareaCorreo], bool]:
        return self._cola.tareas(peticion), self._cola.pausada()


class ControlarCola:
    def __init__(self, cola: IColaNotificaciones) -> None:
        self._cola = cola

    def pausar(self) -> None:
        self._cola.pausar()

    def reanudar(self) -> None:
        self._cola.reanudar()
