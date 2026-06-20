from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from subscriptions.models import (
    CustomerPremiumSubscription,
    LandlordSubscription,
    SubscriptionPlan,
)
from subscriptions.serializers import (
    CustomerPremiumStatusSerializer,
    LandlordSubscriptionSerializer,
    SelectPlanSerializer,
    SubscriptionPlanSerializer,
    UpgradeSerializer,
)
from subscriptions.services import (
    create_landlord_subscription,
    get_active_landlord_subscription,
    get_pending_landlord_subscription,
    initiate_customer_premium_upgrade,
    upgrade_landlord_plan,
)
from payments.subscription_payment import apply_subscription_payment


class PlanListView(generics.ListAPIView):
    """GET /api/v1/subscriptions/plans/ — List active landlord plans for mobile app."""

    serializer_class = SubscriptionPlanSerializer
    permission_classes = [AllowAny]
    queryset = SubscriptionPlan.objects.filter(is_active=True)


class SubscriptionUpgradeView(APIView):
    """
    POST /api/v1/subscriptions/upgrade/
    Unified upgrade endpoint for landlords (plan_id) and customers (upgrade_type).
    Returns transaction_id for the external payment system — no Chapa redirect.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(request=UpgradeSerializer)
    def post(self, request):
        serializer = UpgradeSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = request.user

        if user.role == "landlord":
            return self._upgrade_landlord(user, serializer.validated_data["plan_id"])
        return self._upgrade_customer_premium(user)

    def _upgrade_landlord(self, user, plan_id):
        if not user.email_verified:
            return Response(
                {"detail": "Please verify your email before upgrading."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        plan = SubscriptionPlan.objects.get(id=plan_id)

        if get_active_landlord_subscription(user) or get_pending_landlord_subscription(user):
            subscription = upgrade_landlord_plan(user, plan)
        else:
            subscription = create_landlord_subscription(user, plan)

        user.refresh_from_db()
        return Response(
            {
                "payment_type": "landlord",
                "subscription": LandlordSubscriptionSerializer(subscription).data,
                "transaction_id": subscription.transaction_ref,
                "transaction_ref": subscription.transaction_ref,
                "amount": subscription.amount,
                "account_status": user.account_status,
                "message": (
                    "Plan activated."
                    if subscription.status == LandlordSubscription.Status.ACTIVE
                    else "Pay externally using transaction_id, then call POST /payments/external/verify/."
                ),
            },
            status=status.HTTP_201_CREATED,
        )

    def _upgrade_customer_premium(self, user):
        if user.can_view_premium_listings:
            return Response(
                {"detail": "You already have an active premium subscription."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        subscription, amount = initiate_customer_premium_upgrade(user)

        return Response(
            {
                "payment_type": "customer_premium",
                "transaction_id": subscription.transaction_ref,
                "transaction_ref": subscription.transaction_ref,
                "amount": subscription.amount,
                "subscription_status": subscription.status,
                "payment_status": subscription.payment_status,
                "message": "Pay externally using transaction_id, then call POST /payments/external/verify/.",
            },
            status=status.HTTP_201_CREATED,
        )


class SelectLandlordPlanView(APIView):
    """
    POST /api/v1/subscriptions/landlord/select-plan/
    Landlord selects a plan after email verification (registration fallback).
    Prefer POST /subscriptions/upgrade/ for upgrades.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(request=SelectPlanSerializer, responses={201: LandlordSubscriptionSerializer})
    def post(self, request):
        user = request.user
        if user.role != "landlord":
            return Response(
                {"detail": "Only landlords can select a subscription plan."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not user.email_verified:
            return Response(
                {"detail": "Please verify your email before selecting a plan."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = SelectPlanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan = SubscriptionPlan.objects.get(id=serializer.validated_data["plan_id"])

        if get_active_landlord_subscription(user) or get_pending_landlord_subscription(user):
            subscription = upgrade_landlord_plan(user, plan)
        else:
            subscription = create_landlord_subscription(user, plan)

        user.refresh_from_db()
        return Response(
            {
                "subscription": LandlordSubscriptionSerializer(subscription).data,
                "transaction_id": subscription.transaction_ref,
                "amount": subscription.amount,
                "account_status": user.account_status,
                "message": (
                    "Plan activated."
                    if subscription.status == LandlordSubscription.Status.ACTIVE
                    else "Pay externally using transaction_id, then call POST /payments/external/verify/."
                ),
            },
            status=status.HTTP_201_CREATED,
        )


class MyLandlordSubscriptionView(APIView):
    """GET /api/v1/subscriptions/landlord/me/ — Current landlord subscription."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: LandlordSubscriptionSerializer})
    def get(self, request):
        sub = get_active_landlord_subscription(request.user)
        if not sub:
            sub = get_pending_landlord_subscription(request.user)
        if not sub:
            return Response({"detail": "No subscription found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(LandlordSubscriptionSerializer(sub).data)


class LandlordPaymentVerifyView(APIView):
    """GET /api/v1/subscriptions/landlord/verify/{tx_ref}/ — Verify via external payment record."""

    permission_classes = [IsAuthenticated]

    def get(self, request, tx_ref):
        if not LandlordSubscription.objects.filter(transaction_ref=tx_ref, user=request.user).exists():
            return Response({"detail": "Subscription not found."}, status=status.HTTP_404_NOT_FOUND)

        success, message, _ = apply_subscription_payment(tx_ref)

        if not success:
            return Response(
                {"success": False, "message": message, "transaction_id": tx_ref},
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

        sub = LandlordSubscription.objects.select_related("plan").get(
            transaction_ref=tx_ref, user=request.user
        )
        request.user.refresh_from_db()
        return Response(
            {
                "success": True,
                "message": message,
                "subscription": LandlordSubscriptionSerializer(sub).data,
                "account_status": request.user.account_status,
            }
        )


class CustomerPremiumUpgradeView(APIView):
    """POST /api/v1/subscriptions/customer/premium/upgrade/ — Alias for unified upgrade."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={201: CustomerPremiumStatusSerializer})
    def post(self, request):
        if request.user.role != "customer":
            return Response(
                {"detail": "Only customers can upgrade to premium."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return SubscriptionUpgradeView()._upgrade_customer_premium(request.user)


class CustomerPremiumVerifyView(APIView):
    """GET /api/v1/subscriptions/customer/premium/verify/{tx_ref}/ — Verify via external payment record."""

    permission_classes = [IsAuthenticated]

    def get(self, request, tx_ref):
        if not CustomerPremiumSubscription.objects.filter(
            transaction_ref=tx_ref, user=request.user
        ).exists():
            return Response({"detail": "Subscription not found."}, status=status.HTTP_404_NOT_FOUND)

        success, message, _ = apply_subscription_payment(tx_ref)

        if not success:
            return Response(
                {"success": False, "message": message, "transaction_id": tx_ref},
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

        request.user.refresh_from_db()
        return Response(
            {
                "success": True,
                "message": message,
                "is_premium_customer": request.user.is_premium_customer,
                "premium_until": request.user.premium_until,
            }
        )


class CustomerPremiumStatusView(APIView):
    """GET /api/v1/subscriptions/customer/premium/status/"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        try:
            sub = user.premium_subscription
        except CustomerPremiumSubscription.DoesNotExist:
            sub = None

        return Response(
            {
                "is_premium_customer": user.can_view_premium_listings,
                "premium_until": user.premium_until,
                "subscription_status": sub.status if sub else None,
                "payment_status": sub.payment_status if sub else None,
                "transaction_ref": sub.transaction_ref if sub else None,
                "checkout_url": sub.checkout_url if sub else None,
                "amount": sub.amount if sub else None,
            }
        )
