"""Ritmo de envio, trasladado de las constantes de mass_sender/admin.py.

WhatsApp bloquea los numeros que envian demasiado rapido. El sistema actual
espera 3 segundos entre mensajes y hace una pausa de 120 cada 50; aqui se
conserva ese ritmo, pero como horario: cada mensaje sabe cuantos segundos
despues del lanzamiento le toca salir, y la cola lo programa.
"""

from dataclasses import dataclass

from masssend.domain.shared.errores import DatosInvalidos


@dataclass(frozen=True, slots=True)
class PoliticaEnvio:
    segundos_entre_mensajes: int = 3
    mensajes_por_lote: int = 50
    segundos_entre_lotes: int = 120

    def __post_init__(self) -> None:
        if self.segundos_entre_mensajes < 0 or self.segundos_entre_lotes < 0:
            raise DatosInvalidos("Las esperas no pueden ser negativas.", "politica")
        if self.mensajes_por_lote < 1:
            raise DatosInvalidos("El lote debe tener al menos un mensaje.", "politica")

    def retraso(self, orden: int) -> int:
        """Segundos desde el lanzamiento hasta el mensaje numero orden (desde 0)."""
        if orden < 0:
            raise DatosInvalidos("El orden no puede ser negativo.", "orden")
        lotes_completos = orden // self.mensajes_por_lote
        return orden * self.segundos_entre_mensajes + lotes_completos * self.segundos_entre_lotes

    def duracion(self, total: int) -> int:
        """Segundos hasta que sale el ultimo mensaje."""
        return self.retraso(total - 1) if total > 0 else 0
