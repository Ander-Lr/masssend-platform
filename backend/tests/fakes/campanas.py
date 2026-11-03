from collections.abc import Collection, Sequence
from dataclasses import replace

from masssend.domain.campanas.contacto import Contacto
from masssend.domain.campanas.repositorios import FiltroContactos
from masssend.domain.campanas.telefono import Telefono
from masssend.domain.shared.errores import EstadoInvalido, RecursoNoEncontrado
from masssend.domain.shared.identificadores import IdPublico
from masssend.domain.shared.paginacion import Cursor, Pagina, PeticionPagina


def _copia(contacto: Contacto) -> Contacto:
    return replace(contacto, datos=dict(contacto.datos))


class RepoContactosMemoria:
    """Guarda copias, como una base real: cambiar un objeto no lo persiste."""

    def __init__(self) -> None:
        self.contactos: dict[IdPublico, Contacto] = {}
        self._por_telefono: dict[tuple[IdPublico, Telefono], IdPublico] = {}
        self.busquedas = 0
        self.guardados_en_bloque = 0

    def obtener(self, owner_id: IdPublico, contacto_id: IdPublico) -> Contacto:
        contacto = self.contactos.get(contacto_id)
        if contacto is None or not contacto.pertenece_a(owner_id):
            raise RecursoNoEncontrado("El contacto no existe.")
        return _copia(contacto)

    def buscar_por_telefonos(
        self, owner_id: IdPublico, telefonos: Collection[Telefono]
    ) -> dict[Telefono, Contacto]:
        self.busquedas += 1
        encontrados: dict[Telefono, Contacto] = {}
        for telefono in telefonos:
            contacto_id = self._por_telefono.get((owner_id, telefono))
            if contacto_id is not None:
                encontrados[telefono] = _copia(self.contactos[contacto_id])
        return encontrados

    def guardar(self, contacto: Contacto) -> None:
        clave = (contacto.owner_id, contacto.telefono)
        if self._por_telefono.get(clave, contacto.id) != contacto.id:
            raise EstadoInvalido("El dueño ya tiene ese teléfono.")
        self._por_telefono[clave] = contacto.id
        self.contactos[contacto.id] = _copia(contacto)

    def guardar_varios(self, contactos: Sequence[Contacto]) -> None:
        self.guardados_en_bloque += 1
        for contacto in contactos:
            self.guardar(contacto)

    def eliminar(self, owner_id: IdPublico, contacto_id: IdPublico) -> None:
        contacto = self.obtener(owner_id, contacto_id)
        del self._por_telefono[(owner_id, contacto.telefono)]
        del self.contactos[contacto_id]

    def listar(
        self, owner_id: IdPublico, filtro: FiltroContactos, peticion: PeticionPagina
    ) -> Pagina[Contacto]:
        texto = (filtro.texto or "").lower()
        filas = sorted(
            (
                _copia(c)
                for c in self.contactos.values()
                if c.pertenece_a(owner_id)
                and (not texto or texto in c.nombre.lower() or texto in c.telefono.numero)
                and (filtro.etiqueta is None or filtro.etiqueta in c.etiquetas)
            ),
            key=lambda c: str(c.id),
        )
        if peticion.cursor is not None:
            ultimo = peticion.cursor.valores[0]
            filas = [c for c in filas if str(c.id) > ultimo]
        return Pagina.desde_filas(
            filas[: peticion.limite + 1], peticion, lambda c: Cursor((str(c.id),))
        )
