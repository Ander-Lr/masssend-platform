"""Errores del dominio.

Cada error tiene un codigo estable. El dominio no conoce HTTP: el manejador
de la API traduce cada subclase a su respuesta problem+json.
"""


class ErrorDominio(Exception):
    """Base de todo error esperado del negocio."""

    codigo = "error_dominio"

    def __init__(self, mensaje: str) -> None:
        super().__init__(mensaje)
        self.mensaje = mensaje


class DatosInvalidos(ErrorDominio):
    """Un dato no cumple una regla. Indica el campo afectado."""

    codigo = "datos_invalidos"

    def __init__(self, mensaje: str, campo: str) -> None:
        super().__init__(mensaje)
        self.campo = campo


class NoAutenticado(ErrorDominio):
    """Faltan credenciales o la firma no es valida."""

    codigo = "no_autenticado"


class SinPermiso(ErrorDominio):
    """El usuario esta identificado, pero no puede realizar la accion."""

    codigo = "sin_permiso"


class RecursoNoEncontrado(ErrorDominio):
    """El recurso no existe o pertenece a otro usuario."""

    codigo = "recurso_no_encontrado"


class EstadoInvalido(ErrorDominio):
    """La operacion no se permite en el estado actual del recurso."""

    codigo = "estado_invalido"


class SaldoInsuficiente(ErrorDominio):
    """Los creditos disponibles no alcanzan."""

    codigo = "saldo_insuficiente"

    def __init__(self, mensaje: str, requerido: int, disponible: int) -> None:
        super().__init__(mensaje)
        self.requerido = requerido
        self.disponible = disponible


class DemasiadosIntentos(ErrorDominio):
    """Se supero un limite. Indica los segundos de espera."""

    codigo = "demasiados_intentos"

    def __init__(self, mensaje: str, espera_segundos: int) -> None:
        super().__init__(mensaje)
        self.espera_segundos = espera_segundos


class ServicioNoDisponible(ErrorDominio):
    """Un servicio externo necesario no responde."""

    codigo = "servicio_no_disponible"
