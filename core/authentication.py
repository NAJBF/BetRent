from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed


class PaymentAppTokenAuthentication(BaseAuthentication):
    """
    Static app token auth for external payment webhooks.
    Accepts:
      - Header: X-App-Token: <token>
      - Header: Authorization: Bearer <token>
      - Header: Authorization: Token <token>
    """

    keyword = "Bearer"

    def authenticate(self, request):
        expected = getattr(settings, "PAYMENT_APP_TOKEN", "").strip()
        if not expected:
            raise AuthenticationFailed(
                "PAYMENT_APP_TOKEN is not configured on the server.",
                code="payment_token_not_configured",
            )

        token = self._extract_token(request)
        if not token:
            raise AuthenticationFailed(
                "Missing app token. Send header X-App-Token or Authorization: Bearer <token>.",
                code="payment_token_missing",
            )

        if token != expected:
            raise AuthenticationFailed("Invalid app token.", code="payment_token_invalid")

        # No user object — external system call
        return (None, "payment_app_token")

    def authenticate_header(self, request):
        return 'X-App-Token realm="BetRent External Payments"'

    @staticmethod
    def _extract_token(request):
        token = (
            request.headers.get("X-App-Token")
            or request.headers.get("x-app-token")
            or request.META.get("HTTP_X_APP_TOKEN")
        )
        if token:
            return str(token).strip()

        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth[7:].strip()
        if auth.startswith("Token "):
            return auth[6:].strip()
        return None
