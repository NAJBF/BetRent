from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from .models import User


class RegisterSerializer(serializers.ModelSerializer):
    """Register a new customer or landlord account."""

    password = serializers.CharField(write_only=True, min_length=8)
    role = serializers.ChoiceField(
        choices=[("customer", "Customer"), ("landlord", "Landlord")],
        default="customer",
    )

    class Meta:
        model = User
        fields = [
            "id", "email", "password", "full_name", "phone", "city", "role",
        ]
        read_only_fields = ["id"]

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class LoginSerializer(serializers.Serializer):
    """Authenticate with email + password, returns JWT tokens."""

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(email=attrs["email"], password=attrs["password"])
        if not user:
            raise serializers.ValidationError("Invalid email or password.")
        if not user.is_active:
            raise serializers.ValidationError("Account is deactivated.")
        refresh = RefreshToken.for_user(user)
        return {
            "access_token": str(refresh.access_token),
            "refresh_token": str(refresh),
            "token_type": "bearer",
        }


class TokenRefreshSerializer(serializers.Serializer):
    """Exchange a refresh token for a new token pair."""

    refresh_token = serializers.CharField()

    def validate(self, attrs):
        try:
            refresh = RefreshToken(attrs["refresh_token"])
            return {
                "access_token": str(refresh.access_token),
                "refresh_token": str(refresh),
                "token_type": "bearer",
            }
        except Exception:
            raise serializers.ValidationError("Invalid or expired refresh token.")


class UserProfileSerializer(serializers.ModelSerializer):
    """Read/update the current user's profile."""

    class Meta:
        model = User
        fields = [
            "id", "email", "full_name", "phone", "city", "bio",
            "avatar_url", "role", "is_active", "date_joined",
        ]
        read_only_fields = ["id", "email", "role", "is_active", "date_joined"]


class AdminUserSerializer(serializers.ModelSerializer):
    """Admin view/update of any user — can change role and is_active."""

    class Meta:
        model = User
        fields = [
            "id", "email", "full_name", "phone", "city", "bio",
            "avatar_url", "role", "is_active", "date_joined",
        ]
        read_only_fields = ["id", "email", "date_joined"]


class UserSummarySerializer(serializers.ModelSerializer):
    """Minimal user info for embedding in other serializers."""

    class Meta:
        model = User
        fields = ["id", "full_name", "email", "city", "avatar_url"]
        read_only_fields = fields
