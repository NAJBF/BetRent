from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import NotFound, PermissionDenied

from .models import Payment
from .serializers import (
    PaymentInitiateSerializer,
    PaymentDetailSerializer,
    ChapaWebhookSerializer,
)
from .services import ChapaService
from bookings.models import Booking


class PaymentInitiateView(APIView):
    """POST /api/v1/payments/initiate — Start payment for approved booking."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PaymentInitiateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        booking = Booking.objects.select_related("renter", "listing").get(
            id=serializer.validated_data["booking_id"]
        )

        # Only the renter can initiate payment
        if booking.renter != request.user and request.user.role != "admin":
            raise PermissionDenied("Only the renter can initiate payment.")

        # Create payment record
        payment = Payment.objects.create(
            booking=booking,
            amount=booking.total_price,
            method=serializer.validated_data["method"],
        )

        # Initiate with Chapa (or mock)
        if payment.method == "chapa":
            chapa_result = ChapaService.initiate_payment(
                amount=float(payment.amount),
                tx_ref=payment.transaction_ref,
                email=request.user.email,
                first_name=request.user.full_name.split()[0] if request.user.full_name else "User",
            )
            payment.checkout_url = chapa_result.get("checkout_url", "")
            payment.save(update_fields=["checkout_url"])

        return Response(
            PaymentDetailSerializer(payment).data,
            status=status.HTTP_201_CREATED,
        )


class PaymentVerifyView(APIView):
    """GET /api/v1/payments/verify/{tx_ref} — Check payment status."""

    permission_classes = [IsAuthenticated]

    def get(self, request, tx_ref):
        try:
            payment = Payment.objects.select_related("booking").get(
                transaction_ref=tx_ref
            )
        except Payment.DoesNotExist:
            raise NotFound("Payment not found.")

        # Verify with Chapa if still pending
        if payment.status == "pending" and payment.method == "chapa":
            result = ChapaService.verify_payment(tx_ref)
            if result["status"] == "success":
                payment.status = "completed"
                payment.save(update_fields=["status"])
                # Update booking status to paid
                booking = payment.booking
                booking.status = "paid"
                booking.save(update_fields=["status"])

        return Response(PaymentDetailSerializer(payment).data)


class BookingPaymentView(APIView):
    """GET /api/v1/payments/booking/{booking_id} — Get payment for a booking."""

    permission_classes = [IsAuthenticated]

    def get(self, request, booking_id):
        try:
            payment = Payment.objects.select_related("booking").get(
                booking_id=booking_id
            )
        except Payment.DoesNotExist:
            raise NotFound("Payment not found for this booking.")

        return Response(PaymentDetailSerializer(payment).data)


class ChapaWebhookView(APIView):
    """
    POST /api/v1/payments/webhook/chapa
    Chapa calls this on payment completion. No auth required.
    Auto-completes payment and marks booking as paid.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ChapaWebhookSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        tx_ref = serializer.validated_data["tx_ref"]
        webhook_status = serializer.validated_data["status"]

        try:
            payment = Payment.objects.select_related("booking").get(
                transaction_ref=tx_ref
            )
        except Payment.DoesNotExist:
            raise NotFound("Payment not found.")

        if webhook_status == "success":
            payment.status = "completed"
            payment.save(update_fields=["status"])

            booking = payment.booking
            if booking.status == "approved":
                booking.status = "paid"
                booking.save(update_fields=["status"])
        else:
            payment.status = "failed"
            payment.save(update_fields=["status"])

        return Response({"status": "received"}, status=status.HTTP_200_OK)
