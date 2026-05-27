from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema

from core.permissions import IsAdminRole
from core.pagination import BetRentPagination
from .models import User
from .serializers import (
    RegisterSerializer,
    LoginSerializer,
    TokenRefreshSerializer,
    UserProfileSerializer,
    AdminUserSerializer,
)


# ---------------------------------------------------------------------------
# Auth Views
# ---------------------------------------------------------------------------


class RegisterView(generics.CreateAPIView):
    """POST /api/v1/auth/register — Create a new account."""

    @extend_schema(responses={201: RegisterSerializer})
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {
                "id": str(user.id),
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role,
                "is_active": user.is_active,
            },
            status=status.HTTP_201_CREATED,
        )


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
        """
        Soft-delete: deactivate the account instead of hard-deleting.
        This preserves data integrity (bookings, reviews, payments)
        while preventing the user from logging in again.
        """
        instance.is_active = False
        instance.save(update_fields=["is_active"])

        # Blacklist all outstanding refresh tokens for this user
        try:
            from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
            from rest_framework_simplejwt.tokens import RefreshToken as RefreshTokenObj
            tokens = OutstandingToken.objects.filter(user=instance)
            for token in tokens:
                try:
                    RefreshTokenObj(token.token).blacklist()
                except Exception:
                    pass  # Token already blacklisted or expired
        except ImportError:
            pass  # Token blacklist app not installed; tokens will expire naturally


class AdminUserListView(generics.ListAPIView):
    """GET /api/v1/users/ — Admin: list all users with optional role filter."""

    serializer_class = AdminUserSerializer
    permission_classes = [IsAdminRole]
    pagination_class = BetRentPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["role", "is_active", "city"]

    def get_queryset(self):
        return User.objects.all().order_by("-date_joined")


class AdminUserUpdateView(generics.UpdateAPIView):
    """PUT /api/v1/users/{user_id} — Admin: change role or status."""

    serializer_class = AdminUserSerializer
    permission_classes = [IsAdminRole]
    queryset = User.objects.all()
    lookup_field = "pk"
    lookup_url_kwarg = "user_id"
