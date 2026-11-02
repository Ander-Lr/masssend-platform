from rest_framework.permissions import BasePermission


class MfaEnrollmentPermission(BasePermission):
    """Allow account MFA setup only for the signed-in user or a short first-factor session."""

    def has_permission(self, request, view):
        if request.user and request.user.is_authenticated:
            return True

        session = request.session
        return bool(
            session.get("pending_mfa_enrollment_user_id")
            or session.get("pending_google_enrollment_user_id")
        )


class MfaLoginChallengePermission(BasePermission):
    """Require a password or Google first-factor challenge before accepting a TOTP code."""

    def has_permission(self, request, view):
        session = request.session
        return bool(
            session.get("pending_mfa_login_user_id")
            or session.get("pending_google_mfa_user_id")
        )
