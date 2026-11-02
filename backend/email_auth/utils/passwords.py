"""
Hash y verificación de contraseñas. Se apoya en
django.contrib.auth.hashers (PBKDF2 por defecto) en vez de bcryptjs
como en la práctica de Node, pero cumple el mismo contrato.
"""
from django.contrib.auth.hashers import check_password, make_password


def hash_password(raw_password: str) -> str:
    return make_password(raw_password)


def verify_password(raw_password: str, password_hash: str) -> bool:
    if not password_hash:
        return False
    return check_password(raw_password, password_hash)
