from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.conf import settings
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema

from core.email_service import get_email_debug_info, send_otp_email, store_otp, verify_otp
from core.permissions import IsAdminRole
from core.pagination import BetRentPagination
from .models import User
from .serializers import (
    RegisterSerializer,
    LoginSerializer,
    TokenRefreshSerializer,
    UserProfileSerializer,
    AdminUserSerializer,
    VerifyEmailSerializer,
    ResendOTPSerializer,
    ForgotPasswordSerializer,
    ResetPasswordSerializer,
)


# ---------------------------------------------------------------------------
# Auth Views
# ---------------------------------------------------------------------------


class RegisterView(generics.CreateAPIView):
    """POST /api/v1/auth/register — Create a new account and send OTP email."""

    @extend_schema(responses={201: RegisterSerializer})
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        plan_name = ""
        plan_id = request.data.get("plan_id")
        if plan_id and user.role == "landlord":
            from subscriptions.models import SubscriptionPlan
            try:
                plan = SubscriptionPlan.objects.get(id=plan_id)
                plan_name = plan.name
            except SubscriptionPlan.DoesNotExist:
                pass

        otp = store_otp(user.email, "register")

        payload = {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "email_verified": user.email_verified,
            "account_status": user.account_status,
            "email_config": get_email_debug_info(),
        }
        if user.role == "landlord" and user.landlord_plan_id:
            payload["plan_id"] = str(user.landlord_plan_id)
            payload["plan_name"] = plan_name or getattr(user.landlord_plan, "name", None)

        try:
            result = send_otp_email(
                user.email,
                "register",
                otp,
                extra_context={"plan_name": plan_name, "role": user.role},
            )
            payload["email_sent"] = result["sent"]
            payload["email_via"] = result.get("via")
            if result.get("email_message_id"):
                payload["email_message_id"] = result["email_message_id"]
            if result["sent"]:
                payload["message"] = "Registration successful. Please check your email for the verification code."
            else:
                payload["email_error"] = result.get("error")
                payload["message"] = "Registration successful but email could not be sent."
        except Exception as exc:
            payload["email_sent"] = False
            payload["email_error"] = f"{type(exc).__name__}: {exc}"
            payload["message"] = "Registration successful but email could not be sent."

        return Response(payload, status=status.HTTP_201_CREATED)


class VerifyEmailView(APIView):
    """POST /api/v1/auth/verify-email/ — Verify registration OTP."""

    permission_classes = [AllowAny]

    @extend_schema(request=VerifyEmailSerializer)
    def post(self, request):
        serializer = VerifyEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        otp = serializer.validated_data["otp"]

        if not verify_otp(email, "register", otp):
            return Response(
                {"detail": "Invalid or expired verification code."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        user.email_verified = True

        if user.role == "customer":
            user.account_status = User.AccountStatus.ACTIVE
            user.save(update_fields=["email_verified", "account_status"])
            return Response(
                {
                    "message": "Email verified successfully.",
                    "email_verified": True,
                    "account_status": user.account_status,
                    "next_step": "login",
                }
            )

        # Landlord: check for pre-selected plan or require plan selection
        from django.core.cache import cache
        from subscriptions.models import SubscriptionPlan
        from subscriptions.services import create_landlord_subscription

        pending_plan_id = cache.get(f"pending_plan:{user.id}") or (
            str(user.landlord_plan_id) if user.landlord_plan_id else None
        )
        if pending_plan_id:
            try:
                plan = SubscriptionPlan.objects.get(id=pending_plan_id, is_active=True)
                subscription = create_landlord_subscription(user, plan)
                cache.delete(f"pending_plan:{user.id}")

                user.refresh_from_db()
                return Response(
                    {
                        "message": "Email verified. Plan assigned.",
                        "email_verified": True,
                        "account_status": user.account_status,
                        "plan_id": str(plan.id),
                        "plan_name": plan.name,
                        "next_step": (
                            "login"
                            if user.account_status == User.AccountStatus.ACTIVE
                            else "complete_payment"
                        ),
                        "subscription_status": subscription.status,
                        "payment_status": subscription.payment_status,
                        "transaction_id": subscription.transaction_ref,
                        "transaction_ref": subscription.transaction_ref,
                        "amount": subscription.amount,
                    }
                )
            except SubscriptionPlan.DoesNotExist:
                pass

        # Landlord must select plan
        user.account_status = User.AccountStatus.PENDING_PAYMENT
        user.save(update_fields=["email_verified", "account_status"])
        return Response(
            {
                "message": "Email verified. Please select a subscription plan.",
                "email_verified": True,
                "account_status": user.account_status,
                "next_step": "select_plan",
            }
        )


class ResendOTPView(APIView):
    """POST /api/v1/auth/resend-otp/ — Resend OTP for registration or password reset."""

    permission_classes = [AllowAny]

    @extend_schema(request=ResendOTPSerializer)
    def post(self, request):
        serializer = ResendOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        purpose = serializer.validated_data["purpose"]

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # Don't reveal whether email exists
            return Response({"message": "If the email exists, a new code has been sent."})

        if purpose == "register" and user.email_verified:
            return Response({"detail": "Email is already verified."}, status=status.HTTP_400_BAD_REQUEST)

        otp = store_otp(email, purpose)
        result = send_otp_email(email, purpose, otp, extra_context={"role": user.role})
        if result["sent"]:
            return Response({
                "message": "A new verification code has been sent.",
                "email_sent": True,
                "email_via": result.get("via"),
            })
        return Response(
            {
                "message": "Could not send email.",
                "email_sent": False,
                "email_error": result.get("error"),
                "email_config": get_email_debug_info(),
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


class ForgotPasswordView(APIView):
    """POST /api/v1/auth/forgot-password/ — Send password reset OTP."""

    permission_classes = [AllowAny]

    @extend_schema(request=ForgotPasswordSerializer)
    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        try:
            User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"message": "If the email exists, a reset code has been sent."})

        otp = store_otp(email, "reset_password")
        result = send_otp_email(email, "reset_password", otp)
        if result["sent"]:
            return Response({"message": "If the email exists, a reset code has been sent.", "email_sent": True})
        return Response(
            {
                "message": "Could not send reset email.",
                "email_sent": False,
                "email_error": result.get("error"),
                "email_config": get_email_debug_info(),
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


class ResetPasswordView(APIView):
    """POST /api/v1/auth/reset-password/ — Reset password with OTP."""

    permission_classes = [AllowAny]

    @extend_schema(request=ResetPasswordSerializer)
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        otp = serializer.validated_data["otp"]
        new_password = serializer.validated_data["new_password"]

        if not verify_otp(email, "reset_password", otp):
            return Response(
                {"detail": "Invalid or expired reset code."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        user.set_password(new_password)
        user.save(update_fields=["password"])
        return Response({"message": "Password reset successfully. You can now log in."})


class LoginView(APIView):
    """POST /api/v1/auth/login — Get JWT tokens."""

    permission_classes = [AllowAny]

    @extend_schema(request=LoginSerializer, responses={200: LoginSerializer})
    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


class RefreshTokenView(APIView):
    """POST /api/v1/auth/refresh — Exchange refresh token for new pair."""

    permission_classes = [AllowAny]

    @extend_schema(request=TokenRefreshSerializer, responses={200: TokenRefreshSerializer})
    def post(self, request):
        serializer = TokenRefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# User Management Views
# ---------------------------------------------------------------------------


class UserProfileView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET/PUT /api/v1/users/me — View or update own profile.
    DELETE /api/v1/users/me — Soft-delete (deactivate) own account.
    """

    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])

        try:
            from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
            from rest_framework_simplejwt.tokens import RefreshToken as RefreshTokenObj
            tokens = OutstandingToken.objects.filter(user=instance)
            for token in tokens:
                try:
                    RefreshTokenObj(token.token).blacklist()
                except Exception:
                    pass
        except ImportError:
            pass


class AdminUserListView(generics.ListAPIView):
    """GET /api/v1/users/ — Admin: list all users with optional role filter."""

    serializer_class = AdminUserSerializer
    permission_classes = [IsAdminRole]
    pagination_class = BetRentPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["role", "is_active", "city", "account_status"]

    def get_queryset(self):
        return User.objects.all().order_by("-date_joined")


class AdminUserUpdateView(generics.UpdateAPIView):
    """PUT /api/v1/users/{user_id} — Admin: change role or status."""

    serializer_class = AdminUserSerializer
    permission_classes = [IsAdminRole]
    queryset = User.objects.all()
    lookup_field = "pk"
    lookup_url_kwarg = "user_id"
