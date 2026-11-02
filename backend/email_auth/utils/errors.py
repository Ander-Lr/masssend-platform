"""
Error de dominio único para todo el módulo de email_auth. Los
servicios lanzan AppError con un mensaje en español y un status_code
HTTP; las vistas (DRF) lo capturan y lo devuelven como JSON, igual que
`error.middleware.js` en la práctica de Node.
"""
from rest_framework.exceptions import APIException


class AppError(APIException):
    status_code = 400
    default_detail = "Ocurrió un error inesperado."
    default_code = "app_error"

    def __init__(self, message: str, status_code: int = 400):
        self.status_code = status_code
        super().__init__(detail=message, code=self.default_code)
