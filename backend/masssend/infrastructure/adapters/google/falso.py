from urllib.parse import urlencode

from masssend.application.identidad.puertos import PerfilGoogle


class ProveedorGoogleFalso:
    """Solo para el perfil ci: permite probar el flujo sin una cuenta de Google."""

    def url_autorizacion(self, estado: str) -> str:
        return f"https://google.falso/auth?{urlencode({'state': estado})}"

    def perfil(self, codigo: str) -> PerfilGoogle:
        return PerfilGoogle(f"{codigo}@google.prueba", "Cuenta Google", True)
