from rest_framework import serializers

from subscriptions.models import SubscriptionPlan


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    """Public plan listing for registration / upgrade flows."""

    class Meta:
        model = SubscriptionPlan
        fields = [
            "id",
            "name",
            "slug",
            "plan_type",
            "description",
            "max_posts",
            "max_approvals",
            "max_premium_posts",
            "price",
            "duration_days",
            "is_default",
        ]


class LandlordSubscriptionSerializer(serializers.ModelSerializer):
    plan = SubscriptionPlanSerializer(read_only=True)

    class Meta:
        from subscriptions.models import LandlordSubscription

        model = LandlordSubscription
        fields = [
            "id",
            "plan",
            "status",
            "payment_status",
            "amount",
            "transaction_ref",
            "checkout_url",
            "starts_at",
            "expires_at",
            "posts_used",
            "approvals_used",
            "premium_posts_used",
            "created_at",
        ]


class SelectPlanSerializer(serializers.Serializer):
    plan_id = serializers.UUIDField()

    def validate_plan_id(self, value):
        if not SubscriptionPlan.objects.filter(id=value, is_active=True).exists():
            raise serializers.ValidationError("Plan not found or inactive.")
        return value


class CustomerPremiumStatusSerializer(serializers.Serializer):
    is_premium_customer = serializers.BooleanField()
    premium_until = serializers.DateTimeField(allow_null=True)
    subscription_status = serializers.CharField(allow_null=True)
    payment_status = serializers.CharField(allow_null=True)
    transaction_ref = serializers.CharField(allow_null=True)
    checkout_url = serializers.CharField(allow_null=True)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True)
