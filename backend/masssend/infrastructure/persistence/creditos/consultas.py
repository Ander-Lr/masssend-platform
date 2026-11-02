"""Lecturas directas a DTO: dos consultas por pagina, sin importar el tamano."""

from datetime import datetime

from django.db.models import Q

from billing.models import CreditPack, CreditSpend, PaymentTransaction
from masssend.application.creditos.puertos import Movimiento, Paquete
from masssend.domain.shared.dinero import Dinero
from masssend.domain.shared.errores import DatosInvalidos
from masssend.domain.shared.identificadores import IdPublico
from masssend.domain.shared.paginacion import Cursor, Pagina, PeticionPagina
from masssend.infrastructure.persistence.creditos.repositorios import usuario_de

COMPRA = "compra"
CONSUMO = "consumo"


class ConsultasCreditosDjango:
    def paquetes_activos(self) -> list[Paquete]:
        return [
            Paquete(p.id, p.name, p.credits, Dinero.desde_decimal(p.price_usd))
            for p in CreditPack.objects.filter(is_active=True)
        ]

    def paquete_activo(self, paquete_id: int) -> Paquete | None:
        p = CreditPack.objects.filter(pk=paquete_id, is_active=True).first()
        return Paquete(p.id, p.name, p.credits, Dinero.desde_decimal(p.price_usd)) if p else None

    def movimientos(
        self, dueno_id: IdPublico, peticion: PeticionPagina
    ) -> Pagina[Movimiento]:
        usuario_id = usuario_de(dueno_id)
        cuantas = peticion.limite + 1
        compras = PaymentTransaction.objects.filter(
            _despues(peticion.cursor, COMPRA, "created_at"),
            user_id=usuario_id,
            status=PaymentTransaction.STATUS_APPROVED,
        ).order_by("-created_at", "-id")[:cuantas]
        consumos = CreditSpend.objects.filter(
            _despues(peticion.cursor, CONSUMO, "created_at"), user_id=usuario_id
        ).order_by("-created_at", "-id")[:cuantas]
        filas = [
            *((c.created_at, COMPRA, str(c.id), c.credits, c.provider) for c in compras),
            *((c.created_at, CONSUMO, str(c.id), c.amount, c.reason) for c in consumos),
        ]
        filas.sort(key=lambda f: (-f[0].timestamp(), f[1], _orden_id(f[2])))
        pagina = Pagina.desde_filas(
            filas,
            peticion,
            lambda f: Cursor((f[0].isoformat(), f[1], f[2])),
        )
        return Pagina(
            tuple(Movimiento(f[1], f[3], f[0], f[4]) for f in pagina.elementos),
            pagina.siguiente_cursor,
        )


def _orden_id(valor: str) -> str:
    """Orden descendente estable para ids numericos y UUID."""
    relleno = valor.rjust(40, "0")
    return "".join(chr(0x10FFFF - ord(c)) for c in relleno)


def _despues(cursor: Cursor | None, tipo: str, campo: str) -> Q:
    """Filas posteriores al cursor. En una misma fecha van primero las compras."""
    if cursor is None:
        return Q()
    try:
        fecha_texto, tipo_cursor, id_cursor = cursor.valores
        fecha = datetime.fromisoformat(fecha_texto)
    except ValueError as error:
        raise DatosInvalidos("El cursor no es valido.", "cursor") from error
    anteriores = Q(**{f"{campo}__lt": fecha})
    if tipo == COMPRA and tipo_cursor != COMPRA:
        return anteriores
    mismas = Q(**{campo: fecha})
    if tipo == CONSUMO and tipo_cursor == COMPRA:
        return anteriores | mismas
    if not _id_valido(tipo, id_cursor):
        raise DatosInvalidos("El cursor no es valido.", "cursor")
    return anteriores | (mismas & Q(id__lt=id_cursor))


def _id_valido(tipo: str, valor: str) -> bool:
    if tipo == CONSUMO:
        return valor.isdigit()
    return len(valor) == 36
