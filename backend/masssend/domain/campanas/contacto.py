"""Entidad Contacto: un numero en la libreta de un dueno.

El mismo numero puede estar en la libreta de dos duenos distintos, pero
solo una vez por dueno. Esa unicidad la garantiza el repositorio.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from masssend.domain.campanas.telefono import Telefono
from masssend.domain.shared.errores import DatosInvalidos
from masssend.domain.shared.identificadores import IdPublico

MAX_NOMBRE = 150
MAX_ETIQUETAS = 255


def limpiar_etiquetas(etiquetas: str | Iterable[str]) -> tuple[str, ...]:
    """Acepta "vip, cliente" o una lista. Quita vacias y repetidas, conserva el orden."""
    partes = etiquetas.split(",") if isinstance(etiquetas, str) else etiquetas
    vistas: dict[str, None] = {}
    for parte in partes:
        limpia = parte.strip()
        if limpia:
            vistas.setdefault(limpia, None)
    resultado = tuple(vistas)
    if len(",".join(resultado)) > MAX_ETIQUETAS:
        raise DatosInvalidos(
            f"Las etiquetas no pueden superar {MAX_ETIQUETAS} caracteres.", "etiquetas"
        )
    return resultado


def _limpiar_nombre(nombre: str, telefono: Telefono) -> str:
    """Sin nombre, el contacto se muestra con su numero, como en el sistema actual."""
    limpio = nombre.strip() or telefono.numero
    if len(limpio) > MAX_NOMBRE:
        raise DatosInvalidos(f"El nombre no puede superar {MAX_NOMBRE} caracteres.", "nombre")
    return limpio


@dataclass
class Contacto:
    id: IdPublico
    owner_id: IdPublico
    telefono: Telefono
    nombre: str
    etiquetas: tuple[str, ...] = ()
    datos: dict[str, str] = field(default_factory=dict)
    dado_de_baja: bool = False

    @classmethod
    def nuevo(
        cls,
        id: IdPublico,
        owner_id: IdPublico,
        telefono: Telefono,
        nombre: str = "",
        etiquetas: str | Iterable[str] = (),
        datos: Mapping[str, str] | None = None,
    ) -> "Contacto":
        return cls(
            id,
            owner_id,
            telefono,
            _limpiar_nombre(nombre, telefono),
            limpiar_etiquetas(etiquetas),
            dict(datos or {}),
        )

    def pertenece_a(self, owner_id: IdPublico) -> bool:
        return self.owner_id == owner_id

    def renombrar(self, nombre: str) -> None:
        self.nombre = _limpiar_nombre(nombre, self.telefono)

    def etiquetar(self, etiquetas: str | Iterable[str]) -> None:
        self.etiquetas = limpiar_etiquetas(etiquetas)

    def completar_datos(self, datos: Mapping[str, str]) -> None:
        """Agrega o reemplaza variables para las plantillas; no borra las demas."""
        self.datos = {**self.datos, **datos}

    def tiene_alguna_etiqueta(self, etiquetas: Iterable[str]) -> bool:
        """Sin etiquetas pedidas, todo contacto coincide."""
        buscadas = set(limpiar_etiquetas(etiquetas))
        return not buscadas or bool(buscadas.intersection(self.etiquetas))

    def dar_de_baja(self) -> None:
        """El contacto pidio no recibir mas mensajes. Repetirlo no cambia nada."""
        self.dado_de_baja = True

    def reactivar(self) -> None:
        self.dado_de_baja = False

    @property
    def puede_recibir(self) -> bool:
        return not self.dado_de_baja
