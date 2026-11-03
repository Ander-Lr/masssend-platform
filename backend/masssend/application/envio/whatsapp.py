"""Conexion del numero de WhatsApp de la plataforma. Solo para staff."""

from masssend.application.envio.puertos import EstadoConexion, IConexionWhatsApp
from masssend.domain.campanas.telefono import Telefono


class ConsultarWhatsApp:
    def __init__(self, conexion: IConexionWhatsApp) -> None:
        self._conexion = conexion

    def ejecutar(self) -> EstadoConexion:
        return self._conexion.estado()


class VincularWhatsApp:
    def __init__(self, conexion: IConexionWhatsApp) -> None:
        self._conexion = conexion

    def ejecutar(self, telefono: str) -> str | None:
        """El numero se normaliza igual que un contacto: 09... pasa a 5939..."""
        return self._conexion.solicitar_vinculacion(Telefono.desde_texto(telefono).numero)


class CerrarSesionWhatsApp:
    def __init__(self, conexion: IConexionWhatsApp) -> None:
        self._conexion = conexion

    def ejecutar(self) -> None:
        self._conexion.cerrar_sesion()
