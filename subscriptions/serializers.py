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
    max_posts = serializers.IntegerField(source="plan.max_posts", read_only=True)
    max_premium_posts = serializers.IntegerField(source="plan.max_premium_posts", read_only=True)
    max_approvals = serializers.IntegerField(source="plan.max_approvals", read_only=True)
    posts_remaining = serializers.SerializerMethodField()
    premium_posts_remaining = serializers.SerializerMethodField()
    approvals_remaining = serializers.SerializerMethodField()

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
            "max_posts",
            "max_premium_posts",
            "max_approvals",
            "posts_remaining",
            "premium_posts_remaining",
            "approvals_remaining",
            "created_at",
        ]

    def _usage(self, obj):
        from subscriptions.services import get_landlord_usage

        return get_landlord_usage(obj)

    def get_posts_remaining(self, obj):
        return self._usage(obj)["posts_remaining"]

    def get_premium_posts_remaining(self, obj):
        return self._usage(obj)["premium_posts_remaining"]

    def get_approvals_remaining(self, obj):
        return self._usage(obj)["approvals_remaining"]


class UpgradeSerializer(serializers.Serializer):
    """
    Unified upgrade request.
    Landlords: provide plan_id.
    Customers: set upgrade_type to 'customer_premium' (plan_id not needed).
    """

    plan_id = serializers.UUIDField(required=False, allow_null=True)
    upgrade_type = serializers.ChoiceField(
        choices=[("customer_premium", "Customer Premium")],
        required=False,
    )

    def validate(self, attrs):
        user = self.context["request"].user
        plan_id = attrs.get("plan_id")
        upgrade_type = attrs.get("upgrade_type")

        if user.role == "landlord":
            if not plan_id:
                raise serializers.ValidationError(
                    {"plan_id": "Landlords must provide a plan_id to upgrade."}
                )
            if not SubscriptionPlan.objects.filter(id=plan_id, is_active=True).exists():
                raise serializers.ValidationError({"plan_id": "Plan not found or inactive."})
        elif user.role == "customer":
            if plan_id:
                raise serializers.ValidationError(
                    {"plan_id": "Customers do not select a plan. Use upgrade_type 'customer_premium'."}
                )
            if upgrade_type != "customer_premium":
                raise serializers.ValidationError(
                    {"upgrade_type": "Customers must set upgrade_type to 'customer_premium'."}
                )
        else:
            raise serializers.ValidationError("Only landlords and customers can upgrade.")

        return attrs

class SelectPlanSerializer(serializers.Serializer):
    plan_id = serializers.UUIDField()

    def validate_plan_id(self, value):
        if not SubscriptionPlan.objects.filter(id=value, is_active=True).exists():
            raise serializers.ValidationError("Plan not found or inactive.")
        return value


class VerifyTransactionSerializer(serializers.Serializer):
    transaction_id = serializers.CharField(max_length=100)


class CustomerPremiumStatusSerializer(serializers.Serializer):
    is_premium_customer = serializers.BooleanField()
    premium_until = serializers.DateTimeField(allow_null=True)
    subscription_status = serializers.CharField(allow_null=True)
    payment_status = serializers.CharField(allow_null=True)
    transaction_ref = serializers.CharField(allow_null=True)
    checkout_url = serializers.CharField(allow_null=True)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True)

