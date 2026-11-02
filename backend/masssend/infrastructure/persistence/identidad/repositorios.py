"""Traduce la Cuenta del dominio a auth_user, su perfil y la tabla propia."""

from typing import Any

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import is_password_usable, make_password
from django.db import IntegrityError, transaction
from django.utils import timezone

from email_auth.models import SecurityProfile
from masssend.application.shared.puertos import IGeneradorIds
from masssend.domain.identidad.cuenta import Cuenta
from masssend.domain.identidad.desafio import Desafio, Proposito
from masssend.domain.shared.errores import EstadoInvalido, RecursoNoEncontrado
from masssend.domain.shared.identificadores import IdPublico
from masssend.infrastructure.persistence.identidad.models import (
    CuentaIdentidad,
    DesafioIdentidad,
)

Usuario = get_user_model()


class RepoCuentasDjango:
    def __init__(self, ids: IGeneradorIds) -> None:
        self._ids = ids

    def buscar_por_correo(self, correo: str) -> Cuenta | None:
        usuario = self._usuario(Usuario.objects.all(), correo)
        return self._a_cuenta(usuario) if usuario else None

    def bloquear_por_correo(self, correo: str) -> Cuenta | None:
        usuario = self._usuario(Usuario.objects.select_for_update(), correo)
        return self._a_cuenta(usuario) if usuario else None

    def obtener(self, cuenta_id: IdPublico) -> Cuenta:
        return self._a_cuenta(self._por_id(Usuario.objects.all(), cuenta_id))

    def bloquear(self, cuenta_id: IdPublico) -> Cuenta:
        return self._a_cuenta(self._por_id(Usuario.objects.select_for_update(), cuenta_id))

    def guardar(self, cuenta: Cuenta) -> None:
        try:
            with transaction.atomic():
                identidad = (
                    CuentaIdentidad.objects.select_related("usuario")
                    .filter(public_id=cuenta.id)
                    .first()
                )
                identidad = identidad or self._crear(cuenta)
                self._actualizar(identidad, cuenta)
        except IntegrityError as error:
            raise EstadoInvalido("La cuenta ya existe.") from error

    @staticmethod
    def _usuario(consulta: Any, correo: str) -> Any:
        """Respeta el username exacto: los administradores no usan correo."""
        limpio = correo.strip()
        return (
            consulta.filter(username=limpio).first()
            or consulta.filter(username=limpio.lower()).first()
        )

    @staticmethod
    def _por_id(consulta: Any, cuenta_id: IdPublico) -> Any:
        usuario = consulta.filter(cuenta_identidad__public_id=cuenta_id).first()
        if usuario is None:
            raise RecursoNoEncontrado("La cuenta no existe.")
        return usuario

    def _a_cuenta(self, usuario: Any) -> Cuenta:
        perfil, _ = SecurityProfile.objects.get_or_create(
            user=usuario,
            defaults={
                "status": (
                    SecurityProfile.STATUS_ACTIVE
                    if usuario.is_active
                    else SecurityProfile.STATUS_INACTIVE
                )
            },
        )
        identidad, _ = CuentaIdentidad.objects.get_or_create(
            usuario=usuario, defaults={"public_id": self._ids.nuevo()}
        )
        return Cuenta(
            id=IdPublico(identidad.public_id),
            correo=usuario.email or usuario.username,
            nombre=usuario.get_full_name() or usuario.first_name or usuario.username,
            activa=usuario.is_active,
            es_staff=usuario.is_staff,
            hash_contrasena=usuario.password if is_password_usable(usuario.password) else None,
            codigo_verificacion=perfil.verification_code,
            codigo_expira_en=perfil.verification_code_expires_at,
            intentos_verificacion=perfil.verification_attempts,
            mfa_activo=perfil.mfa_enabled,
            mfa_secreto=perfil.mfa_secret,
            mfa_secreto_pendiente=perfil.pending_mfa_secret,
            ultimo_paso_totp=identidad.ultimo_paso_totp,
            fallos_totp=identidad.fallos_totp,
            bloqueada_hasta=identidad.bloqueada_hasta,
        )

    @staticmethod
    def _crear(cuenta: Cuenta) -> CuentaIdentidad:
        usuario = Usuario.objects.create(
            username=cuenta.correo, email=cuenta.correo, is_active=cuenta.activa
        )
        SecurityProfile.objects.create(user=usuario)
        return CuentaIdentidad.objects.create(usuario=usuario, public_id=cuenta.id)

    @staticmethod
    def _actualizar(identidad: CuentaIdentidad, cuenta: Cuenta) -> None:
        usuario: Any = identidad.usuario
        nombre, _, apellido = cuenta.nombre.partition(" ")
        usuario.first_name, usuario.last_name = nombre, apellido
        usuario.is_active = cuenta.activa
        usuario.password = cuenta.hash_contrasena or make_password(None)
        usuario.save(update_fields=["first_name", "last_name", "is_active", "password"])

        perfil = usuario.security_profile
        if cuenta.activa and perfil.status != SecurityProfile.STATUS_ACTIVE:
            perfil.activated_at = timezone.now()
        perfil.status = (
            SecurityProfile.STATUS_ACTIVE if cuenta.activa else SecurityProfile.STATUS_INACTIVE
        )
        perfil.verification_code = cuenta.codigo_verificacion
        perfil.verification_code_expires_at = cuenta.codigo_expira_en
        perfil.verification_attempts = cuenta.intentos_verificacion
        perfil.mfa_enabled = cuenta.mfa_activo
        perfil.mfa_secret = cuenta.mfa_secreto
        perfil.pending_mfa_secret = cuenta.mfa_secreto_pendiente
        perfil.save()

        identidad.ultimo_paso_totp = cuenta.ultimo_paso_totp
        identidad.fallos_totp = cuenta.fallos_totp
        identidad.bloqueada_hasta = cuenta.bloqueada_hasta
        identidad.save()


class RepoDesafiosDjango:
    def agregar(self, desafio: Desafio) -> None:
        cuenta = (
            CuentaIdentidad.objects.get(public_id=desafio.cuenta_id)
            if desafio.cuenta_id
            else None
        )
        DesafioIdentidad.objects.create(
            id=desafio.id,
            cuenta=cuenta,
            proposito=desafio.proposito.value,
            hash_token=desafio.hash_token,
            expira_en=desafio.expira_en,
        )

    def bloquear_por_hash(self, hash_token: str, proposito: Proposito) -> Desafio | None:
        fila = (
            DesafioIdentidad.objects.select_for_update()
            .filter(hash_token=hash_token, proposito=proposito.value)
            .first()
        )
        if fila is None:
            return None
        cuenta_id = (
            CuentaIdentidad.objects.values_list("public_id", flat=True).get(pk=fila.cuenta_id)
            if fila.cuenta_id
            else None
        )
        return Desafio(
            id=IdPublico(fila.id),
            proposito=Proposito(fila.proposito),
            hash_token=fila.hash_token,
            expira_en=fila.expira_en,
            cuenta_id=IdPublico(cuenta_id) if cuenta_id else None,
            usado_en=fila.usado_en,
        )

    def guardar(self, desafio: Desafio) -> None:
        DesafioIdentidad.objects.filter(pk=desafio.id).update(usado_en=desafio.usado_en)

    def anular_pendientes(self, cuenta_id: IdPublico, proposito: Proposito) -> None:
        DesafioIdentidad.objects.filter(
            cuenta__public_id=cuenta_id, proposito=proposito.value, usado_en__isnull=True
        ).update(usado_en=timezone.now())
