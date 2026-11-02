"""Entidad Cuenta: ciclo de vida, verificacion y doble factor."""

import hmac
from dataclasses import dataclass
from datetime import datetime

from masssend.domain.identidad.politicas import (
    BLOQUEO_TOTP,
    MAX_FALLOS_TOTP,
    MAX_INTENTOS_VERIFICACION,
)
from masssend.domain.shared.errores import (
    DatosInvalidos,
    DemasiadosIntentos,
    EstadoInvalido,
)
from masssend.domain.shared.identificadores import IdPublico


@dataclass
class Cuenta:
    id: IdPublico
    correo: str
    nombre: str
    activa: bool = False
    es_staff: bool = False
    hash_contrasena: str | None = None
    codigo_verificacion: str | None = None
    codigo_expira_en: datetime | None = None
    intentos_verificacion: int = 0
    mfa_activo: bool = False
    mfa_secreto: str | None = None
    mfa_secreto_pendiente: str | None = None
    ultimo_paso_totp: int | None = None
    fallos_totp: int = 0
    bloqueada_hasta: datetime | None = None

    def asignar_codigo(self, codigo: str, expira_en: datetime) -> None:
        self.codigo_verificacion = codigo
        self.codigo_expira_en = expira_en
        self.intentos_verificacion = 0

    def verificar(self, codigo: str, ahora: datetime) -> bool:
        """Activa la cuenta. Devuelve False si el codigo es incorrecto."""
        if self.activa:
            raise EstadoInvalido("La cuenta ya se encuentra activa.")
        if self.intentos_verificacion >= MAX_INTENTOS_VERIFICACION:
            raise DemasiadosIntentos("Solicita un nuevo código.", 60)
        if self.codigo_expira_en is None or self.codigo_expira_en <= ahora:
            raise DatosInvalidos("El código venció. Solicita uno nuevo.", "codigo")
        if not hmac.compare_digest(self.codigo_verificacion or "", codigo):
            self.intentos_verificacion += 1
            return False
        self.activar()
        return True

    def activar(self) -> None:
        self.activa = True
        self.codigo_verificacion = None
        self.codigo_expira_en = None
        self.intentos_verificacion = 0

    def activar_por_google(self) -> None:
        """Google prueba el correo. Una cuenta pendiente pudo crearla un tercero
        con este correo, asi que su contrasena no se conserva."""
        if not self.activa:
            self.hash_contrasena = None
        self.activar()

    def exigir_sin_bloqueo(self, ahora: datetime) -> None:
        if self.bloqueada_hasta is not None and self.bloqueada_hasta > ahora:
            espera = int((self.bloqueada_hasta - ahora).total_seconds()) + 1
            raise DemasiadosIntentos("Demasiados códigos incorrectos.", espera)

    def validar_paso_totp(self, paso: int | None, ahora: datetime) -> bool:
        """Registra el resultado. Un paso ya usado cuenta como fallo."""
        if paso is None or (self.ultimo_paso_totp is not None and paso <= self.ultimo_paso_totp):
            self.fallos_totp += 1
            if self.fallos_totp >= MAX_FALLOS_TOTP:
                self.bloqueada_hasta = ahora + BLOQUEO_TOTP
                self.fallos_totp = 0
            return False
        self.ultimo_paso_totp = paso
        self.fallos_totp = 0
        self.bloqueada_hasta = None
        return True

    def iniciar_mfa(self, secreto: str) -> None:
        if self.mfa_activo:
            raise EstadoInvalido("El doble factor ya está activo.")
        self.mfa_secreto_pendiente = secreto

    def confirmar_mfa(self, paso: int) -> None:
        self.mfa_activo = True
        self.mfa_secreto = self.mfa_secreto_pendiente
        self.mfa_secreto_pendiente = None
        self.ultimo_paso_totp = paso
        self.fallos_totp = 0
        self.bloqueada_hasta = None

    def desactivar_mfa(self) -> None:
        if not self.mfa_activo:
            raise EstadoInvalido("El doble factor no está activo.")
        self.mfa_activo = False
        self.mfa_secreto = None
        self.mfa_secreto_pendiente = None
        self.ultimo_paso_totp = None
