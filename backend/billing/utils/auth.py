"""
Resolución del usuario autenticado (JWT o sesión Django), igual que
`mass_sender.views._get_user`. Se duplica en vez de importar desde
mass_sender a propósito: billing no depende de mass_sender, y
mass_sender ya depende de email_auth/billing solo donde hace falta
(inversión de dependencias entre apps, cada una se sostiene sola).
"""


def get_authenticated_user(request):
    from rest_framework_simplejwt.authentication import JWTAuthentication
    from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

    try:
        result = JWTAuthentication().authenticate(request)
        if result:
            return result[0]
    except (InvalidToken, TokenError):
        pass

    if request.user.is_authenticated:
        return request.user

    return None
