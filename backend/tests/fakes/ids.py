from uuid import UUID

from masssend.domain.shared.identificadores import IdPublico


class GeneradorIdsSecuencial:
    """Entrega UUIDv7 validos y predecibles: el 1, el 2, el 3..."""

    def __init__(self) -> None:
        self._contador = 0

    def nuevo(self) -> IdPublico:
        self._contador += 1
        version_7 = 7 << 76
        variante_rfc = 2 << 62
        return IdPublico(UUID(int=version_7 | variante_rfc | self._contador))
