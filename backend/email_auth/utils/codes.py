"""
Generación de códigos aleatorios. Un único propósito por función
(principio de responsabilidad única): nada aquí sabe de correo, de
usuarios ni de HTTP.
"""
import secrets


def generate_verification_code() -> str:
    """Código numérico de 6 dígitos (100000-999999), igual que la práctica."""
    return str(secrets.randbelow(900000) + 100000)


def generate_recovery_token() -> str:
    """Token largo y aleatorio para el enlace de recuperación de contraseña."""
    return secrets.token_hex(32)
