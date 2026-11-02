from datetime import UTC, datetime, timedelta


class RelojFijo:
    """Reloj controlado por la prueba."""

    def __init__(self, instante: datetime = datetime(2026, 1, 1, tzinfo=UTC)) -> None:
        if instante.tzinfo is None:
            raise ValueError("El reloj exige un instante con zona horaria.")
        self._instante = instante

    def ahora(self) -> datetime:
        return self._instante

    def avanzar(self, tiempo: timedelta) -> None:
        self._instante += tiempo
