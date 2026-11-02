import os
import time
from uuid import UUID

from masssend.domain.shared.identificadores import IdPublico


class GeneradorUuid7:
    """UUIDv7 segun RFC 9562: Python 3.11 aun no lo incluye."""

    def nuevo(self) -> IdPublico:
        milisegundos = time.time_ns() // 1_000_000
        azar = int.from_bytes(os.urandom(10), "big")
        valor = milisegundos << 80
        valor |= 0x7 << 76
        valor |= ((azar >> 62) & 0xFFF) << 64
        valor |= 0b10 << 62
        valor |= azar & ((1 << 62) - 1)
        return IdPublico(UUID(int=valor))
