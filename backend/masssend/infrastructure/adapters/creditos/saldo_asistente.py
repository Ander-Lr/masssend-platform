"""Implementacion real de ISaldoCreditos: el asistente lee el saldo sin conocer creditos."""

from masssend.application.creditos.consultas import ConsultarSaldo
from masssend.application.ia.puertos import SaldoCuenta
from masssend.domain.shared.identificadores import IdPublico


class SaldoCreditosLocal:
    def __init__(self, consultar: ConsultarSaldo) -> None:
        self._consultar = consultar

    def saldo(self, owner_id: IdPublico) -> SaldoCuenta:
        actual = self._consultar.ejecutar(owner_id)
        return SaldoCuenta(actual.disponible, actual.reservado)
