from rest_framework import serializers

from payments.models import ExternalPaymentRecord, Payment
from bookings.models import Booking


class PaymentInitiateSerializer(serializers.Serializer):
    """Legacy — booking payments are no longer used in the app flow."""

    booking_id = serializers.UUIDField()
    method = serializers.ChoiceField(
        choices=Payment.Method.choices,
        default="chapa",
    )

    def validate_booking_id(self, value):
        raise serializers.ValidationError(
            "Booking payments are not required. Customers book for free; "
            "only subscription upgrades require payment."
        )


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


class ExternalPaymentRecordSerializer(serializers.ModelSerializer):
    """Incoming payment record from external payment system."""

    app_token = serializers.CharField(
        write_only=True,
        required=False,
        help_text=(
            "Same value as PAYMENT_APP_TOKEN on the server. "
            "You can send this in the body (Swagger) or use the X-App-Token header."
        ),
    )
    transaction_id = serializers.CharField(max_length=100)
    payer_name = serializers.CharField(max_length=255)
    payment_status = serializers.ChoiceField(choices=ExternalPaymentRecord.Status.choices)
    amount = serializers.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        model = ExternalPaymentRecord
        fields = [
            "app_token",
            "id",
            "transaction_id",
            "payer_name",
            "payment_status",
            "amount",
            "processed",
            "created_at",
        ]
        read_only_fields = ["id", "processed", "created_at"]

    def validate(self, attrs):
        attrs.pop("app_token", None)
        return attrs

    def create(self, validated_data):
        transaction_id = validated_data["transaction_id"]
        record, created = ExternalPaymentRecord.objects.update_or_create(
            transaction_id=transaction_id,
            defaults={
                "payer_name": validated_data["payer_name"],
                "payment_status": validated_data["payment_status"],
                "amount": validated_data["amount"],
            },
        )
        if not created and validated_data["payment_status"] == ExternalPaymentRecord.Status.COMPLETED:
            record.processed = False
            record.save(update_fields=["processed"])
        return record


class VerifyTransactionRequestSerializer(serializers.Serializer):
    transaction_id = serializers.CharField(max_length=100)
