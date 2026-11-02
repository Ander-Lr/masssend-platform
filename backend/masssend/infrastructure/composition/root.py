"""Raiz de composicion: el unico lugar donde se instancian adaptadores."""

from django.conf import settings

from masssend.application.shared.puertos import (
    IAleatorio,
    IGeneradorIds,
    IReloj,
    IUnidadDeTrabajo,
)
from masssend.application.shared.salud import ComprobarSalud
from masssend.infrastructure.adapters.sistema.aleatorio import AleatorioSeguro
from masssend.infrastructure.adapters.sistema.ids import GeneradorUuid7
from masssend.infrastructure.adapters.sistema.reloj import RelojSistema
from masssend.infrastructure.adapters.sistema.salud import ComprobadorBaseDatos, ComprobadorCache
from masssend.infrastructure.persistence.unidad_de_trabajo import UnidadDeTrabajoDjango


class ContenedorRaiz:
    def reloj(self) -> IReloj:
        return RelojSistema()

    def generador_ids(self) -> IGeneradorIds:
        return GeneradorUuid7()

    def aleatorio(self) -> IAleatorio:
        return AleatorioSeguro()

    def unidad_de_trabajo(self) -> IUnidadDeTrabajo:
        return UnidadDeTrabajoDjango()

    def comprobar_salud(self) -> ComprobarSalud:
        return ComprobarSalud(
            [ComprobadorBaseDatos(), ComprobadorCache()],
            settings.API_VERSION,
        )


contenedor = ContenedorRaiz()
