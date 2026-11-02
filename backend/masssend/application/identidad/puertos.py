from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from masssend.domain.shared.identificadores import IdPublico


@dataclass(frozen=True, slots=True)
class ParTokens:
    acceso: str
    renovacion: str


@dataclass(frozen=True, slots=True)
class PerfilGoogle:
    correo: str
    nombre: str
    verificado: bool


class IHasherContrasenas(Protocol):
    def generar(self, contrasena: str) -> str: ...

    def verificar(self, contrasena: str, hash_guardado: str | None) -> bool:
        """Sin hash tarda lo mismo, para no revelar si la cuenta existe."""
        ...


class ITotp(Protocol):
    def generar_secreto(self) -> str: ...

    def uri(self, secreto: str, correo: str) -> str: ...

    def qr(self, uri: str) -> str:
        """Devuelve la imagen como data URL."""
        ...

    def paso_valido(self, secreto: str, codigo: str, ahora: datetime) -> int | None:
        """Devuelve el paso de tiempo que coincide, o None."""
        ...


class IColaCorreos(Protocol):
    def encolar_verificacion(self, nombre: str, correo: str, codigo: str) -> None: ...

    def encolar_recuperacion(
        self, nombre: str, correo: str, token: str, minutos: int
    ) -> None: ...


class IEmisorTokens(Protocol):
    def emitir(self, cuenta_id: IdPublico) -> ParTokens: ...

    def renovar(self, renovacion: str) -> ParTokens:
        """Rota el token. Lanza NoAutenticado si es invalido o ya se uso."""
        ...

    def revocar(self, renovacion: str) -> None: ...

    def revocar_todos(self, cuenta_id: IdPublico) -> None: ...


class IProveedorGoogle(Protocol):
    def url_autorizacion(self, estado: str) -> str: ...

    def perfil(self, codigo: str) -> PerfilGoogle:
        """Lanza ServicioNoDisponible si Google no responde."""
        ...
