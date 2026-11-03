"""Estadisticas del usuario: mensajes, entregas, campanas y contactos."""

from datetime import date
from typing import Any

from rest_framework.request import Request
from rest_framework.response import Response

from masssend.application.envio.consultas import Reporte
from masssend.domain.shared.errores import DatosInvalidos
from masssend.infrastructure.composition.envio import contenedor_envio as envio
from masssend.interfaces.http.shared.vistas import VistaApi, cuenta_actual


def _fecha(request: Request, clave: str) -> date | None:
    valor = request.query_params.get(clave)
    if not valor:
        return None
    try:
        return date.fromisoformat(valor)
    except ValueError as error:
        raise DatosInvalidos("Usa el formato AAAA-MM-DD.", clave) from error


def reporte_json(reporte: Reporte) -> dict[str, Any]:
    return {
        "desde": reporte.periodo.desde.isoformat(),
        "hasta": reporte.periodo.hasta.isoformat(),
        "resumen": {
            "enviados": reporte.enviados,
            "recibidos": reporte.recibidos,
            "entregados": reporte.entregados,
            "leidos": reporte.leidos,
            "fallidos": reporte.fallidos,
            "pendientes": reporte.pendientes,
            "tasa_entrega": reporte.tasa_entrega,
            "tasa_lectura": reporte.tasa_lectura,
        },
        "por_dia": [
            {"dia": d.dia.isoformat(), "enviados": d.enviados, "recibidos": d.recibidos}
            for d in reporte.por_dia
        ],
        "campanas": reporte.campanas,
        "contactos": {"total": reporte.contactos, "dados_de_baja": reporte.contactos_de_baja},
    }


class ReportesVista(VistaApi):
    def get(self, request: Request) -> Response:
        reporte = envio.generar_reporte().ejecutar(
            cuenta_actual(request), _fecha(request, "desde"), _fecha(request, "hasta")
        )
        return Response(reporte_json(reporte))
