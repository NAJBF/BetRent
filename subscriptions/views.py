from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from core.permissions import IsAdminRole
from payments.services import ChapaService
from subscriptions.models import (
    CustomerPremiumSubscription,
    LandlordSubscription,
    PlatformSettings,
    SubscriptionPlan,
)
from subscriptions.serializers import (
    CustomerPremiumStatusSerializer,
    LandlordSubscriptionSerializer,
    SelectPlanSerializer,
    SubscriptionPlanSerializer,
)
from subscriptions.services import (
    activate_customer_premium,
    activate_landlord_subscription,
    create_landlord_subscription,
    get_active_landlord_subscription,
    get_pending_landlord_subscription,
)


class PlanListView(generics.ListAPIView):
    """GET /api/v1/subscriptions/plans/ — List active landlord plans."""

    serializer_class = SubscriptionPlanSerializer
    permission_classes = [AllowAny]
    queryset = SubscriptionPlan.objects.filter(is_active=True)


class SelectLandlordPlanView(APIView):
    """
    POST /api/v1/subscriptions/landlord/select-plan/
    Landlord selects a plan after email verification.
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

        # Block if already has active subscription
        if get_active_landlord_subscription(user):
            return Response(
                {"detail": "You already have an active subscription."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = SelectPlanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan = SubscriptionPlan.objects.get(id=serializer.validated_data["plan_id"])

        subscription = create_landlord_subscription(user, plan)

        # Initiate Chapa payment for paid plans
        if plan.price > 0 and plan.plan_type != SubscriptionPlan.PlanType.FREE:
            chapa_result = ChapaService.initiate_payment(
                amount=float(plan.price),
                tx_ref=subscription.transaction_ref,
                email=user.email,
                first_name=user.full_name.split()[0] if user.full_name else "User",
            )
            subscription.checkout_url = chapa_result.get("checkout_url", "")
            subscription.save(update_fields=["checkout_url"])

        user.refresh_from_db()
        return Response(
            {
                "subscription": LandlordSubscriptionSerializer(subscription).data,
                "account_status": user.account_status,
                "message": (
                    "Plan activated."
                    if subscription.status == LandlordSubscription.Status.ACTIVE
                    else "Plan selected. Complete payment or wait for admin approval."
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
    """GET /api/v1/subscriptions/landlord/verify/{tx_ref}/ — Verify landlord plan payment."""

    permission_classes = [IsAuthenticated]

    def get(self, request, tx_ref):
        try:
            subscription = LandlordSubscription.objects.select_related("plan").get(
                transaction_ref=tx_ref,
                user=request.user,
            )
        except LandlordSubscription.DoesNotExist:
            return Response({"detail": "Subscription not found."}, status=status.HTTP_404_NOT_FOUND)

        if subscription.payment_status == LandlordSubscription.PaymentStatus.COMPLETED:
            return Response(LandlordSubscriptionSerializer(subscription).data)

        # Try Chapa verify; admin approval is the fallback
        result = ChapaService.verify_payment(tx_ref)
        if result.get("status") == "success":
            activate_landlord_subscription(subscription)
        else:
            return Response(
                {
                    "detail": "Payment not yet verified. Awaiting admin approval or payment completion.",
                    "subscription": LandlordSubscriptionSerializer(subscription).data,
                },
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

        subscription.refresh_from_db()
        return Response(LandlordSubscriptionSerializer(subscription).data)


class CustomerPremiumUpgradeView(APIView):
    """
    POST /api/v1/subscriptions/customer/premium/upgrade/
    Initiate customer premium subscription (Chapa + admin approval fallback).
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={201: CustomerPremiumStatusSerializer})
    def post(self, request):
        user = request.user
        if user.role != "customer":
            return Response(
                {"detail": "Only customers can upgrade to premium."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if user.can_view_premium_listings:
            return Response(
                {"detail": "You already have an active premium subscription."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        settings = PlatformSettings.get_settings()
        subscription, _ = CustomerPremiumSubscription.objects.get_or_create(
            user=user,
            defaults={
                "amount": settings.customer_premium_price,
                "status": CustomerPremiumSubscription.Status.PENDING,
                "payment_status": CustomerPremiumSubscription.PaymentStatus.PENDING,
            },
        )

        if subscription.payment_status != CustomerPremiumSubscription.PaymentStatus.COMPLETED:
            subscription.amount = settings.customer_premium_price
            subscription.status = CustomerPremiumSubscription.Status.PENDING
            subscription.payment_status = CustomerPremiumSubscription.PaymentStatus.PENDING
            subscription.save()

            chapa_result = ChapaService.initiate_payment(
                amount=float(settings.customer_premium_price),
                tx_ref=subscription.transaction_ref,
                email=user.email,
                first_name=user.full_name.split()[0] if user.full_name else "User",
            )
            subscription.checkout_url = chapa_result.get("checkout_url", "")
            subscription.save(update_fields=["checkout_url"])

        return Response(
            {
                "is_premium_customer": user.is_premium_customer,
                "premium_until": user.premium_until,
                "subscription_status": subscription.status,
                "payment_status": subscription.payment_status,
                "transaction_ref": subscription.transaction_ref,
                "checkout_url": subscription.checkout_url,
                "amount": subscription.amount,
                "message": "Complete payment or wait for admin approval to access premium listings.",
            },
            status=status.HTTP_201_CREATED,
        )


class CustomerPremiumVerifyView(APIView):
    """GET /api/v1/subscriptions/customer/premium/verify/{tx_ref}/"""

    permission_classes = [IsAuthenticated]

    def get(self, request, tx_ref):
        try:
            subscription = CustomerPremiumSubscription.objects.get(
                transaction_ref=tx_ref,
                user=request.user,
            )
        except CustomerPremiumSubscription.DoesNotExist:
            return Response({"detail": "Subscription not found."}, status=status.HTTP_404_NOT_FOUND)

        if subscription.payment_status == CustomerPremiumSubscription.PaymentStatus.COMPLETED:
            user = request.user
            return Response(
                {
                    "is_premium_customer": user.is_premium_customer,
                    "premium_until": user.premium_until,
                    "subscription_status": subscription.status,
                    "payment_status": subscription.payment_status,
                }
            )

        result = ChapaService.verify_payment(tx_ref)
        if result.get("status") == "success":
            activate_customer_premium(subscription)
            request.user.refresh_from_db()
            return Response(
                {
                    "is_premium_customer": request.user.is_premium_customer,
                    "premium_until": request.user.premium_until,
                    "subscription_status": subscription.status,
                    "payment_status": subscription.payment_status,
                }
            )

        return Response(
            {
                "detail": "Payment not yet verified. Awaiting admin approval or payment completion.",
                "subscription_status": subscription.status,
                "payment_status": subscription.payment_status,
            },
            status=status.HTTP_402_PAYMENT_REQUIRED,
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
