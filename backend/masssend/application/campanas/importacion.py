"""Importacion de contactos por lotes, trasladada de ContactService.importar_lote.

El sistema actual cargaba todo el CSV y hacia una consulta por fila. Aqui
las filas llegan como iterable, se procesan de a LOTE y cada lote hace una
sola busqueda y un solo guardado. Asi 10.000 filas no agotan la memoria.
Una fila invalida no detiene el resto: se informa en rechazadas.
"""

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from itertools import islice

from masssend.application.shared.puertos import IGeneradorIds, IUnidadDeTrabajo
from masssend.domain.campanas.contacto import Contacto, limpiar_etiquetas
from masssend.domain.campanas.repositorios import IRepoContactos
from masssend.domain.campanas.telefono import Telefono
from masssend.domain.shared.errores import DatosInvalidos
from masssend.domain.shared.identificadores import IdPublico

LOTE = 500


@dataclass(frozen=True, slots=True)
class FilaImportacion:
    """Una fila tal como llega del CSV. numero es la fila que ve el usuario."""

    numero: int
    telefono: str
    nombre: str = ""
    etiquetas: str = ""
    notas: str = ""


@dataclass(frozen=True, slots=True)
class FilaRechazada:
    numero: int
    telefono: str
    campo: str
    mensaje: str


@dataclass
class ResultadoImportacion:
    creados: int = 0
    actualizados: int = 0
    rechazadas: list[FilaRechazada] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.creados + self.actualizados + len(self.rechazadas)


def _en_lotes(filas: Iterable[FilaImportacion], tamano: int) -> Iterator[list[FilaImportacion]]:
    iterador = iter(filas)
    while lote := list(islice(iterador, tamano)):
        yield lote


class ImportarContactos:
    def __init__(
        self,
        contactos: IRepoContactos,
        ids: IGeneradorIds,
        uow: IUnidadDeTrabajo,
        tamano_lote: int = LOTE,
    ) -> None:
        if tamano_lote < 1:
            raise ValueError("El tamano del lote debe ser positivo.")
        self._contactos = contactos
        self._ids = ids
        self._uow = uow
        self._tamano_lote = tamano_lote

    def ejecutar(
        self, owner_id: IdPublico, filas: Iterable[FilaImportacion]
    ) -> ResultadoImportacion:
        resultado = ResultadoImportacion()
        for lote in _en_lotes(filas, self._tamano_lote):
            self._procesar_lote(owner_id, lote, resultado)
        return resultado

    def _procesar_lote(
        self,
        owner_id: IdPublico,
        lote: list[FilaImportacion],
        resultado: ResultadoImportacion,
    ) -> None:
        validas: list[tuple[FilaImportacion, Telefono]] = []
        for fila in lote:
            try:
                validas.append((fila, Telefono.desde_texto(fila.telefono)))
            except DatosInvalidos as error:
                resultado.rechazadas.append(
                    FilaRechazada(fila.numero, fila.telefono, error.campo, error.mensaje)
                )
        if not validas:
            return
        with self._uow:
            telefonos = {telefono for _, telefono in validas}
            existentes = self._contactos.buscar_por_telefonos(owner_id, telefonos)
            pendientes: dict[Telefono, Contacto] = {}
            for fila, telefono in validas:
                contacto = pendientes.get(telefono) or existentes.get(telefono)
                try:
                    if contacto is None:
                        contacto = self._nuevo(owner_id, fila, telefono)
                        resultado.creados += 1
                    else:
                        self._actualizar(contacto, fila)
                        resultado.actualizados += 1
                except DatosInvalidos as error:
                    resultado.rechazadas.append(
                        FilaRechazada(fila.numero, fila.telefono, error.campo, error.mensaje)
                    )
                    continue
                pendientes[telefono] = contacto
            self._contactos.guardar_varios(list(pendientes.values()))

    def _nuevo(self, owner_id: IdPublico, fila: FilaImportacion, telefono: Telefono) -> Contacto:
        datos = {"notas": fila.notas.strip()} if fila.notas.strip() else None
        return Contacto.nuevo(
            self._ids.nuevo(), owner_id, telefono, fila.nombre, fila.etiquetas, datos
        )

    @staticmethod
    def _actualizar(contacto: Contacto, fila: FilaImportacion) -> None:
        """Mismo criterio que update_or_create: la fila manda sobre nombre y etiquetas.

        Valida todo antes de cambiar algo, para no dejar el contacto a medias.
        """
        etiquetas = limpiar_etiquetas(fila.etiquetas)
        contacto.renombrar(fila.nombre)
        contacto.etiquetar(etiquetas)
        if fila.notas.strip():
            contacto.completar_datos({"notas": fila.notas.strip()})
