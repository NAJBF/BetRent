from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import NotFound, PermissionDenied
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiResponse

from core.authentication import PaymentAppTokenAuthentication
from payments.models import ExternalPaymentRecord, Payment
from payments.subscription_payment import apply_subscription_payment
from .serializers import (
    ExternalPaymentRecordSerializer,
    PaymentDetailSerializer,
    PaymentInitiateSerializer,
    VerifyTransactionRequestSerializer,
)
from bookings.models import Booking


class PaymentInitiateView(APIView):
    """
    POST /api/v1/payments/initiate/
    Deprecated — customers book for free. Use /api/v1/subscriptions/upgrade/ instead.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        return Response(
            {
                "detail": "Booking payments are not required. Customers book for free. "
                "Only subscription upgrades require payment via /api/v1/subscriptions/upgrade/."
            },
            status=status.HTTP_410_GONE,
        )


class ExternalPaymentRecordView(APIView):
    """
    POST /api/v1/payments/external/record/
    External payment system submits transaction details here.
    Auth: X-App-Token header (same value as PAYMENT_APP_TOKEN on server).
    """

    authentication_classes = [PaymentAppTokenAuthentication]
    permission_classes = [AllowAny]

    @extend_schema(
        auth=["PaymentAppToken"],
        request=ExternalPaymentRecordSerializer,
        responses={
            201: ExternalPaymentRecordSerializer,
            401: OpenApiResponse(description="Missing or invalid X-App-Token"),
        },
        examples=[
            OpenApiExample(
                "Record completed landlord payment",
                value={
                    "transaction_id": "LSUB-ABC123DEF456",
                    "payer_name": "John Landlord",
                    "payment_status": "completed",
                    "amount": "500.00",
                },
                request_only=True,
            ),
        ],
    )
    def post(self, request):
        serializer = ExternalPaymentRecordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        record = serializer.save()
        return Response(
            ExternalPaymentRecordSerializer(record).data,
            status=status.HTTP_201_CREATED,
        )


class ExternalPaymentVerifyView(APIView):
    """
    POST /api/v1/payments/external/verify/
    Verify a subscription payment by transaction ID and activate the user plan.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=VerifyTransactionRequestSerializer,
        examples=[
            OpenApiExample(
                "Verify subscription payment",
                value={"transaction_id": "LSUB-ABC123DEF456"},
                request_only=True,
            ),
        ],
    )
    def post(self, request):
        serializer = VerifyTransactionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        transaction_id = serializer.validated_data["transaction_id"]

        if not _user_owns_transaction(request.user, transaction_id):
            return Response(
                {"detail": "This transaction does not belong to your account."},
                status=status.HTTP_403_FORBIDDEN,
            )

        success, message, payment_type = apply_subscription_payment(transaction_id)
        request.user.refresh_from_db()

        if not success:
            return Response(
                {
                    "success": False,
                    "message": message,
                    "transaction_id": transaction_id,
                },
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

        response = {
            "success": True,
            "message": message,
            "transaction_id": transaction_id,
            "payment_type": payment_type,
            "account_status": request.user.account_status,
            "is_premium_customer": request.user.is_premium_customer,
            "premium_until": request.user.premium_until,
        }

        from subscriptions.models import LandlordSubscription
        from subscriptions.serializers import LandlordSubscriptionSerializer

        if payment_type == "landlord":
            sub = LandlordSubscription.objects.filter(
                transaction_ref=transaction_id, user=request.user
            ).select_related("plan").first()
            if sub:
                response["subscription"] = LandlordSubscriptionSerializer(sub).data

        return Response(response, status=status.HTTP_200_OK)


def _user_owns_transaction(user, transaction_id):
    from subscriptions.models import CustomerPremiumSubscription, LandlordSubscription

    if LandlordSubscription.objects.filter(transaction_ref=transaction_id, user=user).exists():
        return True
    if CustomerPremiumSubscription.objects.filter(transaction_ref=transaction_id, user=user).exists():
        return True
    return user.role == "admin"


class PaymentVerifyView(APIView):
    """GET /api/v1/payments/verify/{tx_ref}/ — Legacy booking payment verify."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: PaymentDetailSerializer})
    def get(self, request, tx_ref):
        try:
            payment = Payment.objects.select_related("booking").get(transaction_ref=tx_ref)
        except Payment.DoesNotExist:
            raise NotFound("Payment not found.")

        return Response(PaymentDetailSerializer(payment).data)


class BookingPaymentView(APIView):
    """GET /api/v1/payments/booking/{booking_id}/ — Legacy booking payment lookup."""

    permission_classes = [IsAuthenticated]

    def get(self, request, booking_id):
        try:
            payment = Payment.objects.select_related("booking").get(booking_id=booking_id)
        except Payment.DoesNotExist:
            raise NotFound("No payment record for this booking. Booking payments are not required.")

        return Response(PaymentDetailSerializer(payment).data)


class ChapaWebhookView(APIView):
    """Legacy Chapa webhook for booking payments."""

    permission_classes = [AllowAny]

    def post(self, request):
        return Response({"status": "received"}, status=status.HTTP_200_OK)


class PaymentManualUpdateView(APIView):
    """Legacy manual booking payment update."""

    permission_classes = [IsAuthenticated]

    def put(self, request, payment_id):
        raise NotFound("Booking payment updates are no longer supported.")
