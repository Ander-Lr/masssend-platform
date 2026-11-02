from dataclasses import replace

from masssend.domain.creditos.billetera import Billetera
from masssend.domain.creditos.reserva import Reserva
from masssend.domain.shared.errores import RecursoNoEncontrado
from masssend.domain.shared.identificadores import IdPublico


class RepoReservasMemoria:
    def __init__(self) -> None:
        self.reservas: dict[IdPublico, Reserva] = {}
        self.consumos: set[tuple[IdPublico, IdPublico]] = set()

    def agregar(self, reserva: Reserva) -> None:
        self.reservas[reserva.id] = replace(reserva)

    def obtener(self, reserva_id: IdPublico) -> Reserva:
        if reserva_id not in self.reservas:
            raise RecursoNoEncontrado("La reserva no existe.")
        return replace(self.reservas[reserva_id])

    def bloquear(self, reserva_id: IdPublico) -> Reserva:
        return self.obtener(reserva_id)

    def guardar(self, reserva: Reserva) -> None:
        self.reservas[reserva.id] = replace(reserva)

    def ya_consumido(self, reserva_id: IdPublico, mensaje_id: IdPublico) -> bool:
        return (reserva_id, mensaje_id) in self.consumos

    def registrar_consumo(self, reserva: Reserva, mensaje_id: IdPublico) -> None:
        self.consumos.add((reserva.id, mensaje_id))


class RepoBilleterasMemoria:
    def __init__(self, reservas: RepoReservasMemoria, saldo: int = 0) -> None:
        self._reservas = reservas
        self._saldo_inicial = saldo
        self.saldos: dict[IdPublico, int] = {}

    def obtener(self, dueno_id: IdPublico) -> Billetera:
        reservado = sum(
            r.restante for r in self._reservas.reservas.values() if r.dueno_id == dueno_id
        )
        return Billetera(dueno_id, self.saldos.get(dueno_id, self._saldo_inicial), reservado)

    def bloquear(self, dueno_id: IdPublico) -> Billetera:
        return self.obtener(dueno_id)

    def guardar(self, billetera: Billetera) -> None:
        self.saldos[billetera.dueno_id] = billetera.saldo
