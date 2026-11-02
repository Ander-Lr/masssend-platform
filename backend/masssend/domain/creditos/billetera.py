"""Billetera: el saldo baja cuando el mensaje sale, no al lanzar la campana."""

from dataclasses import dataclass

from masssend.domain.shared.errores import DatosInvalidos, EstadoInvalido, SaldoInsuficiente
from masssend.domain.shared.identificadores import IdPublico


def _exigir_positivo(cantidad: int) -> None:
    if cantidad <= 0:
        raise DatosInvalidos("La cantidad debe ser mayor que cero.", "cantidad")


@dataclass
class Billetera:
    dueno_id: IdPublico
    saldo: int
    reservado: int = 0

    def __post_init__(self) -> None:
        if self.saldo < 0 or self.reservado < 0:
            raise EstadoInvalido("La billetera no puede quedar en negativo.")

    @property
    def disponible(self) -> int:
        """El sistema actual gasta sin mirar reservas: nunca se informa negativo."""
        return max(self.saldo - self.reservado, 0)

    def reservar(self, cantidad: int) -> bool:
        """Devuelve False si no alcanza: es un resultado esperado, no un fallo."""
        _exigir_positivo(cantidad)
        if cantidad > self.disponible:
            return False
        self.reservado += cantidad
        return True

    def consumir(self) -> None:
        if self.reservado == 0:
            raise EstadoInvalido("La billetera no tiene créditos reservados.")
        if self.saldo == 0:
            raise SaldoInsuficiente("El saldo se agotó.", requerido=1, disponible=0)
        self.saldo -= 1
        self.reservado -= 1

    def liberar(self, cantidad: int) -> None:
        if cantidad > self.reservado:
            raise EstadoInvalido("No se puede liberar más de lo reservado.")
        self.reservado -= cantidad

    def acreditar(self, cantidad: int) -> None:
        _exigir_positivo(cantidad)
        self.saldo += cantidad
