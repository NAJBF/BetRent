from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from .models import User


class RegisterSerializer(serializers.ModelSerializer):
    """Register a new customer or landlord account. Sends OTP email for verification."""

    password = serializers.CharField(write_only=True, min_length=8)
    role = serializers.ChoiceField(
        choices=[("customer", "Customer"), ("landlord", "Landlord")],
        default="customer",
    )
    plan_id = serializers.UUIDField(required=False, allow_null=True, write_only=True)

    class Meta:
        model = User
        fields = [
            "id", "email", "password", "full_name", "phone", "city", "role", "plan_id",
        ]
        read_only_fields = ["id"]

    def validate_plan_id(self, value):
        if value is None:
            return value
        from subscriptions.models import SubscriptionPlan
        if not SubscriptionPlan.objects.filter(id=value, is_active=True).exists():
            raise serializers.ValidationError("Plan not found or inactive.")
        return value

    def validate(self, attrs):
        role = attrs.get("role", User.Role.CUSTOMER)
        plan_id = attrs.get("plan_id")

        if role == User.Role.LANDLORD and not plan_id:
            raise serializers.ValidationError(
                {"plan_id": "Landlords must select a subscription plan during registration."}
            )

        if role == User.Role.CUSTOMER:
            attrs.pop("plan_id", None)

        return attrs

    def create(self, validated_data):
        plan_id = validated_data.pop("plan_id", None)
        role = validated_data.pop("role", User.Role.CUSTOMER)
        user = User.objects.create_user(
            **validated_data,
            role=role,
            is_active=True,
            email_verified=False,
            account_status=User.AccountStatus.PENDING_EMAIL,
        )

        # Store selected plan_id in cache for post-verification plan selection
        if plan_id and role == "landlord":
            from django.core.cache import cache
            cache.set(f"pending_plan:{user.id}", str(plan_id), 86400)

        return user


class VerifyEmailSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(min_length=6, max_length=6)


class ResendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    purpose = serializers.ChoiceField(choices=["register", "reset_password"], default="register")


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(min_length=6, max_length=6)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_new_password(self, value):
        validate_password(value)
        return value


class LoginSerializer(serializers.Serializer):
    """Authenticate with email + password, returns JWT tokens."""

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    access_token = serializers.CharField(read_only=True)
    refresh_token = serializers.CharField(read_only=True)
    token_type = serializers.CharField(read_only=True)

    def validate(self, attrs):
        request = self.context.get("request")
        user = authenticate(request=request, email=attrs["email"], password=attrs["password"])
        if not user:
            raise serializers.ValidationError("Invalid email or password.")
        if not user.is_active:
            raise serializers.ValidationError("Account is deactivated.")
        refresh = RefreshToken.for_user(user)
        return {
            "access_token": str(refresh.access_token),
            "refresh_token": str(refresh),
            "token_type": "bearer",
            "email_verified": user.email_verified,
            "account_status": user.account_status,
            "role": user.role,
        }


class TokenRefreshSerializer(serializers.Serializer):
    """Exchange a refresh token for a new token pair."""

    refresh_token = serializers.CharField()
    access_token = serializers.CharField(read_only=True)
    token_type = serializers.CharField(read_only=True)

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

    can_post_listings = serializers.BooleanField(read_only=True)
    can_view_premium_listings = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id", "email", "full_name", "phone", "city", "bio",
            "avatar_url", "role", "is_active", "date_joined",
            "email_verified", "account_status", "is_premium_customer",
            "premium_until", "can_post_listings", "can_view_premium_listings",
        ]
        read_only_fields = [
            "id", "email", "role", "is_active", "date_joined",
            "email_verified", "account_status", "is_premium_customer",
            "premium_until", "can_post_listings", "can_view_premium_listings",
        ]


class AdminUserSerializer(serializers.ModelSerializer):
    """Admin view/update of any user — can change role and is_active."""

    class Meta:
        model = User
        fields = [
            "id", "email", "full_name", "phone", "city", "bio",
            "avatar_url", "role", "is_active", "date_joined",
            "email_verified", "account_status", "is_premium_customer", "premium_until",
        ]
        read_only_fields = ["id", "email", "date_joined"]


class UserSummarySerializer(serializers.ModelSerializer):
    """Minimal user info for embedding in other serializers. No contact details by default."""

    class Meta:
        model = User
        fields = ["id", "full_name", "city", "avatar_url"]
        read_only_fields = fields


class RenterContactSerializer(serializers.ModelSerializer):
    """Full renter contact — only shown to landlord after booking approval."""

    class Meta:
        model = User
        fields = ["id", "full_name", "email", "phone", "city", "avatar_url"]
        read_only_fields = fields
