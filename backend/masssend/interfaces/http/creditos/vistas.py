from dataclasses import asdict
from typing import Any

from rest_framework.request import Request
from rest_framework.response import Response

from masssend.application.creditos.puertos import Movimiento, Paquete
from masssend.infrastructure.composition.creditos import contenedor_creditos as creditos
from masssend.interfaces.http.shared.paginacion import peticion_pagina, respuesta_pagina
from masssend.interfaces.http.shared.vistas import VistaApi, cuenta_actual


def paquete_json(paquete: Paquete) -> dict[str, Any]:
    return {
        "id": paquete.id,
        "nombre": paquete.nombre,
        "creditos": paquete.creditos,
        "precio": f"{paquete.precio.como_decimal():.2f}",
        "moneda": paquete.precio.moneda,
    }


def movimiento_json(movimiento: Movimiento) -> dict[str, Any]:
    return {
        "tipo": movimiento.tipo,
        "creditos": movimiento.creditos,
        "fecha": movimiento.fecha.isoformat(),
        "detalle": movimiento.detalle,
    }


class PaquetesVista(VistaApi):
    def get(self, request: Request) -> Response:
        cuenta_actual(request)
        paquetes = creditos.listar_paquetes().ejecutar()
        return Response({"datos": [paquete_json(p) for p in paquetes]})


class SaldoVista(VistaApi):
    def get(self, request: Request) -> Response:
        return Response(asdict(creditos.consultar_saldo().ejecutar(cuenta_actual(request))))


class MovimientosVista(VistaApi):
    def get(self, request: Request) -> Response:
        pagina = creditos.listar_movimientos().ejecutar(
            cuenta_actual(request), peticion_pagina(request)
        )
        return respuesta_pagina(pagina, movimiento_json)
