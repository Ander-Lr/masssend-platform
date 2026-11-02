from dataclasses import dataclass

from masssend.application.shared.puertos import IComprobadorDependencia
from masssend.application.shared.salud import ComprobarSalud


@dataclass
class Dependencia:
    nombre: str
    requerida: bool
    responde: bool

    def comprobar(self) -> bool:
        return self.responde


def ejecutar(*dependencias: IComprobadorDependencia) -> tuple[str, bool, dict[str, str]]:
    resultado = ComprobarSalud(dependencias, "1.0.0").ejecutar()
    return resultado.estado, resultado.disponible, resultado.dependencias


def test_todo_responde() -> None:
    assert ejecutar(Dependencia("base", True, True)) == ("ok", True, {"base": "ok"})


def test_sin_la_base_la_api_esta_caida() -> None:
    assert ejecutar(Dependencia("base", True, False))[:2] == ("caido", False)


def test_sin_una_dependencia_opcional_sigue_disponible() -> None:
    estado, disponible, dependencias = ejecutar(
        Dependencia("base", True, True), Dependencia("cache", False, False)
    )
    assert (estado, disponible) == ("degradado", True)
    assert dependencias == {"base": "ok", "cache": "caido"}


def test_caido_prevalece_sobre_degradado_en_cualquier_orden() -> None:
    requerida = Dependencia("base", True, False)
    opcional = Dependencia("cache", False, False)
    assert ejecutar(requerida, opcional)[0] == "caido"
    assert ejecutar(opcional, requerida)[0] == "caido"


def test_informa_la_version() -> None:
    assert ComprobarSalud([], "1.2.3").ejecutar().version == "1.2.3"
