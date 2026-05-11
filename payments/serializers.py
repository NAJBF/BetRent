from rest_framework import serializers
from .models import Payment
from bookings.models import Booking


class PaymentInitiateSerializer(serializers.Serializer):
    """Initiate a payment for an approved booking."""

    booking_id = serializers.UUIDField()
    method = serializers.ChoiceField(
        choices=Payment.Method.choices,
        default="chapa",
    )

    def validate_booking_id(self, value):
        try:
            booking = Booking.objects.get(id=value)
        except Booking.DoesNotExist:
            raise serializers.ValidationError("Booking not found.")

        if booking.status != "approved":
            raise serializers.ValidationError(
                "Payment can only be initiated for approved bookings."
            )

        # Check if payment already exists
        if hasattr(booking, "payment"):
            raise serializers.ValidationError(
                "Payment already exists for this booking."
            )

        return value


class PaymentDetailSerializer(serializers.ModelSerializer):
    """Payment detail with booking info."""

    booking_id = serializers.UUIDField(source="booking.id", read_only=True)
    booking_status = serializers.CharField(source="booking.status", read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id", "booking_id", "booking_status", "amount", "method",
            "status", "transaction_ref", "checkout_url", "created_at",
        ]


class ChapaWebhookSerializer(serializers.Serializer):
    """Handle Chapa payment webhook callback."""

    tx_ref = serializers.CharField()
    status = serializers.CharField()
