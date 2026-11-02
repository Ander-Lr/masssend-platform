"""Fakes del modulo de identidad."""

from dataclasses import replace
from datetime import datetime

from masssend.application.identidad.puertos import ParTokens, PerfilGoogle
from masssend.domain.identidad.cuenta import Cuenta
from masssend.domain.identidad.desafio import Desafio, Proposito
from masssend.domain.shared.errores import NoAutenticado, RecursoNoEncontrado
from masssend.domain.shared.identificadores import IdPublico


class RepoCuentasMemoria:
    def __init__(self) -> None:
        self.cuentas: dict[IdPublico, Cuenta] = {}

    def buscar_por_correo(self, correo: str) -> Cuenta | None:
        encontrada = next((c for c in self.cuentas.values() if c.correo == correo), None)
        return replace(encontrada) if encontrada else None

    def bloquear_por_correo(self, correo: str) -> Cuenta | None:
        return self.buscar_por_correo(correo)

    def obtener(self, cuenta_id: IdPublico) -> Cuenta:
        if cuenta_id not in self.cuentas:
            raise RecursoNoEncontrado("La cuenta no existe.")
        return replace(self.cuentas[cuenta_id])

    def bloquear(self, cuenta_id: IdPublico) -> Cuenta:
        return self.obtener(cuenta_id)

    def guardar(self, cuenta: Cuenta) -> None:
        self.cuentas[cuenta.id] = replace(cuenta)


class RepoDesafiosMemoria:
    def __init__(self) -> None:
        self.desafios: dict[IdPublico, Desafio] = {}

    def agregar(self, desafio: Desafio) -> None:
        self.desafios[desafio.id] = desafio

    def bloquear_por_hash(self, hash_token: str, proposito: Proposito) -> Desafio | None:
        return next(
            (
                replace(d)
                for d in self.desafios.values()
                if d.hash_token == hash_token and d.proposito == proposito
            ),
            None,
        )

    def guardar(self, desafio: Desafio) -> None:
        self.desafios[desafio.id] = replace(desafio)

    def anular_pendientes(self, cuenta_id: IdPublico, proposito: Proposito) -> None:
        for desafio in self.desafios.values():
            if desafio.cuenta_id == cuenta_id and desafio.proposito == proposito:
                desafio.usado_en = desafio.expira_en


class HasherFalso:
    def generar(self, contrasena: str) -> str:
        return f"hash:{contrasena}"

    def verificar(self, contrasena: str, hash_guardado: str | None) -> bool:
        return hash_guardado == f"hash:{contrasena}"


class TotpFalso:
    """Acepta el codigo '100000 + paso', y devuelve ese paso."""

    def generar_secreto(self) -> str:
        return "SECRETO"

    def uri(self, secreto: str, correo: str) -> str:
        return f"otpauth://{correo}?secret={secreto}"

    def qr(self, uri: str) -> str:
        return f"data:{uri}"

    def paso_valido(self, secreto: str, codigo: str, ahora: datetime) -> int | None:
        if not secreto or not codigo.isdigit() or int(codigo) <= 100000:
            return None
        return int(codigo) - 100000


class ColaCorreosFalsa:
    def __init__(self) -> None:
        self.codigos: list[tuple[str, str]] = []
        self.recuperaciones: list[tuple[str, str]] = []

    def encolar_verificacion(self, nombre: str, correo: str, codigo: str) -> None:
        self.codigos.append((correo, codigo))

    def encolar_recuperacion(self, nombre: str, correo: str, token: str, minutos: int) -> None:
        self.recuperaciones.append((correo, token))


class EmisorTokensFalso:
    def __init__(self) -> None:
        self._contador = 0
        self.vigentes: dict[str, IdPublico] = {}
        self.revocadas: list[IdPublico] = []

    def emitir(self, cuenta_id: IdPublico) -> ParTokens:
        self._contador += 1
        renovacion = f"renovacion-{self._contador}"
        self.vigentes[renovacion] = cuenta_id
        return ParTokens(f"acceso-{self._contador}", renovacion)

    def renovar(self, renovacion: str) -> ParTokens:
        if renovacion not in self.vigentes:
            raise NoAutenticado("Token inválido.")
        return self.emitir(self.vigentes.pop(renovacion))

    def revocar(self, renovacion: str) -> None:
        self.vigentes.pop(renovacion, None)

    def revocar_todos(self, cuenta_id: IdPublico) -> None:
        self.revocadas.append(cuenta_id)
        self.vigentes = {t: c for t, c in self.vigentes.items() if c != cuenta_id}


class ProveedorGoogleFalso:
    def __init__(self, perfil: PerfilGoogle) -> None:
        self.perfil_devuelto = perfil

    def url_autorizacion(self, estado: str) -> str:
        return f"https://google.prueba/auth?state={estado}"

    def perfil(self, codigo: str) -> PerfilGoogle:
        return self.perfil_devuelto
