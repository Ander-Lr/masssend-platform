"""Dinero en centavos, para que los pagos no sufran redondeos de float."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from masssend.domain.shared.errores import DatosInvalidos


@dataclass(frozen=True, slots=True)
class Dinero:
    centavos: int
    moneda: str = "USD"

    def __post_init__(self) -> None:
        if self.centavos < 0:
            raise DatosInvalidos("El monto no puede ser negativo.", "monto")
        if len(self.moneda) != 3 or not self.moneda.isalpha() or not self.moneda.isupper():
            raise DatosInvalidos("La moneda debe tener tres letras mayusculas.", "moneda")

    @classmethod
    def desde_decimal(cls, monto: Decimal | str, moneda: str = "USD") -> "Dinero":
        """Crea el monto desde un valor con dos decimales como maximo."""
        try:
            valor = Decimal(monto)
            centavos = valor * 100
        except InvalidOperation as error:
            raise DatosInvalidos("El monto no es valido.", "monto") from error
        if not valor.is_finite() or centavos != centavos.to_integral_value():
            raise DatosInvalidos("El monto admite dos decimales como maximo.", "monto")
        return cls(int(centavos), moneda)

    def como_decimal(self) -> Decimal:
        return Decimal(self.centavos) / 100

    def sumar(self, otro: "Dinero") -> "Dinero":
        self._exigir_misma_moneda(otro)
        return Dinero(self.centavos + otro.centavos, self.moneda)

    def restar(self, otro: "Dinero") -> "Dinero":
        self._exigir_misma_moneda(otro)
        return Dinero(self.centavos - otro.centavos, self.moneda)

    def multiplicar(self, cantidad: int) -> "Dinero":
        return Dinero(self.centavos * cantidad, self.moneda)

    def _exigir_misma_moneda(self, otro: "Dinero") -> None:
        if self.moneda != otro.moneda:
            raise DatosInvalidos("No se pueden operar monedas distintas.", "moneda")
