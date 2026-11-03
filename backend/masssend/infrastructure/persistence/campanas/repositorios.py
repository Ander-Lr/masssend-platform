"""Repositorio de contactos sobre la tabla del sistema actual."""

import logging
from collections.abc import Collection, Sequence
from typing import Any
from uuid import UUID

from django.db import IntegrityError
from django.db.models import Q, QuerySet

from masssend.domain.campanas.contacto import Contacto, limpiar_etiquetas
from masssend.domain.campanas.repositorios import FiltroContactos
from masssend.domain.campanas.telefono import Telefono
from masssend.domain.shared.errores import DatosInvalidos, EstadoInvalido, RecursoNoEncontrado
from masssend.domain.shared.identificadores import IdPublico
from masssend.domain.shared.paginacion import Cursor, Pagina, PeticionPagina
from masssend.infrastructure.persistence.campanas.models import ContactoFila
from masssend.infrastructure.persistence.identidad.models import CuentaIdentidad

logger = logging.getLogger(__name__)

CAMPOS_EDITABLES = ["full_name", "tags", "custom_data", "is_opted_out"]
TELEFONO_DUPLICADO = "Ya tienes un contacto con ese teléfono."


def _telefono(numero: str) -> Telefono:
    """Un numero viejo que hoy no pasaria la validacion igual se muestra."""
    try:
        return Telefono(numero)
    except DatosInvalidos:
        try:
            return Telefono.desde_texto(numero)
        except DatosInvalidos:
            logger.warning("Contacto con telefono fuera de formato: %s", numero)
            telefono = object.__new__(Telefono)
            object.__setattr__(telefono, "numero", numero)
            return telefono


def _contacto(fila: ContactoFila, owner_id: IdPublico) -> Contacto:
    telefono = _telefono(fila.phone_number)
    datos = fila.custom_data if isinstance(fila.custom_data, dict) else {}
    return Contacto(
        IdPublico(fila.public_id),
        owner_id,
        telefono,
        (fila.full_name or "").strip() or telefono.numero,
        limpiar_etiquetas(fila.tags or ""),
        {str(clave): str(valor) for clave, valor in datos.items()},
        fila.is_opted_out,
    )


def _campos(contacto: Contacto) -> dict[str, Any]:
    return {
        "full_name": contacto.nombre,
        "tags": ",".join(contacto.etiquetas) or None,
        "custom_data": dict(contacto.datos) or None,
        "is_opted_out": contacto.dado_de_baja,
    }


def _cursor_id(cursor: Cursor) -> UUID:
    try:
        (valor,) = cursor.valores
        return UUID(valor)
    except ValueError as error:
        raise DatosInvalidos("El cursor no es valido.", "cursor") from error


class RepoContactosDjango:
    def __init__(self) -> None:
        self._usuarios: dict[IdPublico, int] = {}

    def _usuario(self, owner_id: IdPublico) -> int:
        if owner_id not in self._usuarios:
            usuario_id = (
                CuentaIdentidad.objects.filter(public_id=owner_id)
                .values_list("usuario_id", flat=True)
                .first()
            )
            if usuario_id is None:
                raise RecursoNoEncontrado("La cuenta no existe.")
            self._usuarios[owner_id] = usuario_id
        return self._usuarios[owner_id]

    def _propios(self, owner_id: IdPublico) -> QuerySet[ContactoFila]:
        return ContactoFila.objects.filter(usuario_id=self._usuario(owner_id))

    def obtener(self, owner_id: IdPublico, contacto_id: IdPublico) -> Contacto:
        fila = self._propios(owner_id).filter(public_id=contacto_id).first()
        if fila is None:
            raise RecursoNoEncontrado("El contacto no existe.")
        return _contacto(fila, owner_id)

    def buscar_por_telefonos(
        self, owner_id: IdPublico, telefonos: Collection[Telefono]
    ) -> dict[Telefono, Contacto]:
        numeros = [telefono.numero for telefono in telefonos]
        filas = self._propios(owner_id).filter(phone_number__in=numeros)
        return {(c := _contacto(fila, owner_id)).telefono: c for fila in filas}

    def guardar(self, contacto: Contacto) -> None:
        campos = _campos(contacto)
        try:
            actualizadas = (
                self._propios(contacto.owner_id).filter(public_id=contacto.id).update(**campos)
            )
            if not actualizadas:
                ContactoFila.objects.create(
                    public_id=contacto.id,
                    usuario_id=self._usuario(contacto.owner_id),
                    phone_number=contacto.telefono.numero,
                    **campos,
                )
        except IntegrityError as error:
            raise EstadoInvalido(TELEFONO_DUPLICADO) from error

    def guardar_varios(self, contactos: Sequence[Contacto]) -> None:
        """Tres consultas por lote, sin importar cuantos contactos traiga."""
        if not contactos:
            return
        claves = dict(
            ContactoFila.objects.filter(public_id__in=[c.id for c in contactos]).values_list(
                "public_id", "id"
            )
        )
        nuevos: list[ContactoFila] = []
        existentes: list[ContactoFila] = []
        for contacto in contactos:
            fila = ContactoFila(
                id=claves.get(contacto.id),
                public_id=contacto.id,
                usuario_id=self._usuario(contacto.owner_id),
                phone_number=contacto.telefono.numero,
                **_campos(contacto),
            )
            (existentes if fila.id is not None else nuevos).append(fila)
        try:
            ContactoFila.objects.bulk_create(nuevos, batch_size=500)
            ContactoFila.objects.bulk_update(existentes, CAMPOS_EDITABLES, batch_size=500)
        except IntegrityError as error:
            raise EstadoInvalido(TELEFONO_DUPLICADO) from error

    def eliminar(self, owner_id: IdPublico, contacto_id: IdPublico) -> None:
        borrados, _ = self._propios(owner_id).filter(public_id=contacto_id).delete()
        if not borrados:
            raise RecursoNoEncontrado("El contacto no existe.")

    def eliminar_varios(self, owner_id: IdPublico, contacto_ids: Collection[IdPublico]) -> int:
        borrados, _ = self._propios(owner_id).filter(public_id__in=list(contacto_ids)).delete()
        return borrados

    def listar(
        self, owner_id: IdPublico, filtro: FiltroContactos, peticion: PeticionPagina
    ) -> Pagina[Contacto]:
        consulta = self._propios(owner_id)
        if filtro.texto:
            consulta = consulta.filter(
                Q(full_name__icontains=filtro.texto) | Q(phone_number__contains=filtro.texto)
            )
        if filtro.etiqueta:
            etiqueta = _escapar_regex(filtro.etiqueta.strip())
            consulta = consulta.filter(tags__iregex=rf"(^|,)\s*{etiqueta}\s*(,|$)")
        if peticion.cursor is not None:
            consulta = consulta.filter(public_id__lt=_cursor_id(peticion.cursor))
        filas = consulta.order_by("-public_id")[: peticion.limite + 1]
        return Pagina.desde_filas(
            [_contacto(fila, owner_id) for fila in filas],
            peticion,
            lambda c: Cursor((str(c.id),)),
        )

    def etiquetas(self, owner_id: IdPublico) -> list[str]:
        textos = (
            self._propios(owner_id)
            .exclude(tags__isnull=True)
            .exclude(tags="")
            .values_list("tags", flat=True)
            .distinct()
        )
        return sorted({etiqueta for texto in textos for etiqueta in limpiar_etiquetas(texto)})


def _escapar_regex(texto: str) -> str:
    """re.escape produce secuencias que PostgreSQL no entiende; se escapan solo las especiales."""
    return "".join(f"\\{c}" if c in r".^$*+?()[]{}|\\" else c for c in texto)
