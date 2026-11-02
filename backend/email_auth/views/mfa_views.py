"""HTTP adapters for MFA enrollment and two-factor sign-in."""
from django.contrib.auth import get_user_model, login as django_login, logout as django_logout
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.authentication import SessionAuthentication

from ..permissions import MfaEnrollmentPermission, MfaLoginChallengePermission
from ..services import mfa_service
from ..utils.errors import AppError

User = get_user_model()
AUTHENTICATION_CLASSES = [JWTAuthentication, SessionAuthentication]


def _session_user(request, key):
    user_id = request.session.get(key)
    if not user_id:
        return None
    return User.objects.filter(pk=user_id, is_active=True).first()


def _mfa_subject(request):
    if request.user and request.user.is_authenticated:
        return request.user, "authenticated"

    user = _session_user(request, "pending_mfa_enrollment_user_id")
    if user:
        return user, "password_enrollment"

    user = _session_user(request, "pending_google_enrollment_user_id")
    if user:
        return user, "google_enrollment"

    raise AppError("Inicia sesión para configurar la autenticación en dos pasos.", 401)


def _google_token_response(user, profile):
    refresh = RefreshToken.for_user(user)
    refresh["email"] = profile["email"]
    refresh["nombre"] = profile.get("nombre", "")
    refresh["foto"] = profile.get("foto", "")
    refresh["google_id"] = profile.get("google_id", "")
    refresh["is_staff"] = user.is_staff
    return {
        "token": str(refresh.access_token),
        "nombre": profile.get("nombre", ""),
        "foto": profile.get("foto", ""),
        "email": profile["email"],
        "isStaff": user.is_staff,
    }


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def login_step1(request):
    user, payload = mfa_service.login_first_step(
        email=request.data.get("email"),
        password=request.data.get("password"),
    )

    django_logout(request)
    if payload.get("requiresMfa"):
        request.session["pending_mfa_login_user_id"] = user.pk
    elif payload.get("requiresMfaEnrollment"):
        request.session["pending_mfa_enrollment_user_id"] = user.pk
    request.session.cycle_key()
    request.session.set_expiry(600)
    return Response(payload, status=200)


@api_view(["POST"])
@authentication_classes([])
@permission_classes([MfaLoginChallengePermission])
def login_step2(request):
    user = _session_user(request, "pending_mfa_login_user_id")
    if not user:
        raise AppError("El primer paso de inicio de sesión expiró. Vuelve a ingresar.", 401)

    user, payload = mfa_service.verify_mfa_login(
        user=user,
        code=request.data.get("code"),
    )
    request.session.pop("pending_mfa_login_user_id", None)
    django_login(request, user)
    request.session.set_expiry(None)  # los 10 min eran solo para el reto MFA
    return Response({**payload, "user": payload["user"]}, status=200)


@api_view(["POST"])
@authentication_classes([])
@permission_classes([MfaLoginChallengePermission])
def google_login_verify(request):
    pending = request.session.get("pending_google_profile")
    user = _session_user(request, "pending_google_mfa_user_id")
    if not pending or not user:
        raise AppError("El primer paso de Google expiró. Vuelve a iniciar sesión.", 401)

    mfa_service.verify_mfa_login(user=user, code=request.data.get("code"))
    result = _google_token_response(user, pending)
    request.session.pop("pending_google_mfa_user_id", None)
    request.session.pop("pending_google_profile", None)
    return Response({"message": "Inicio de sesión completado con segundo factor.", **result}, status=200)


@api_view(["POST"])
@authentication_classes(AUTHENTICATION_CLASSES)
@permission_classes([MfaEnrollmentPermission])
def setup(request):
    user, _flow = _mfa_subject(request)
    return Response(mfa_service.start_mfa_setup(user), status=200)


@api_view(["POST"])
@authentication_classes(AUTHENTICATION_CLASSES)
@permission_classes([MfaEnrollmentPermission])
def confirm(request):
    user, flow = _mfa_subject(request)
    pending = request.session.get("pending_google_profile") if flow == "google_enrollment" else None
    if flow == "google_enrollment" and (
        not pending or pending.get("email", "").lower() != (user.email or user.username).lower()
    ):
        raise AppError("La sesión de Google expiró o no coincide. Vuelve a iniciar sesión.", 401)

    result = mfa_service.confirm_mfa_setup(user=user, code=request.data.get("code"))

    if flow == "password_enrollment":
        request.session.pop("pending_mfa_enrollment_user_id", None)
        django_login(request, user)
        request.session.set_expiry(None)  # los 10 min eran solo para el reto MFA
    elif flow == "google_enrollment":
        result.update(_google_token_response(user, pending))
        request.session.pop("pending_google_enrollment_user_id", None)
        request.session.pop("pending_google_profile", None)

    return Response(result, status=200)


@api_view(["GET"])
@authentication_classes(AUTHENTICATION_CLASSES)
@permission_classes([MfaEnrollmentPermission])
def status(request):
    user, _flow = _mfa_subject(request)
    return Response(mfa_service.get_mfa_status(user), status=200)


@api_view(["POST"])
@authentication_classes(AUTHENTICATION_CLASSES)
@permission_classes([IsAuthenticated])
def disable(request):
    return Response(mfa_service.disable_mfa(
        user=request.user,
        password=request.data.get("password"),
    ), status=200)
