from django.contrib.auth.hashers import (
    UNUSABLE_PASSWORD_PREFIX,
    check_password,
    make_password,
)


class HasherDjango:
    def generar(self, contrasena: str) -> str:
        return make_password(contrasena)

    def verificar(self, contrasena: str, hash_guardado: str | None) -> bool:
        # Un hash inutilizable hace que Django calcule igual: el tiempo no delata la cuenta.
        return check_password(contrasena, hash_guardado or UNUSABLE_PASSWORD_PREFIX)
