from rest_framework import serializers
from .models import Booking
from listings.models import Listing
from accounts.serializers import UserSummarySerializer


class BookingCreateSerializer(serializers.ModelSerializer):
    """
    Create a booking request.
    Auto-calculates total_price based on duration tier.
    Validates date conflicts and self-booking prevention.
    """

    listing_id = serializers.UUIDField(write_only=True)

    class Meta:
        model = Booking
        fields = [
            "id", "listing_id", "start_date", "end_date", "note",
            "total_price", "deposit_amount", "status", "created_at",
        ]
        read_only_fields = [
            "id", "total_price", "deposit_amount", "status", "created_at",
        ]

    def validate_listing_id(self, value):
        try:
            listing = Listing.objects.get(id=value, is_active=True)
        except Listing.DoesNotExist:
            raise serializers.ValidationError("Listing not found or inactive.")
        return value

    def validate(self, attrs):
        listing_id = attrs["listing_id"]
        start_date = attrs["start_date"]
        end_date = attrs["end_date"]
        user = self.context["request"].user

        if start_date >= end_date:
            raise serializers.ValidationError(
                {"end_date": "End date must be after start date."}
            )

        listing = Listing.objects.get(id=listing_id)

        # Self-booking prevention
        if listing.owner == user:
            raise serializers.ValidationError(
                "You cannot book your own listing."
            )

        # Date conflict detection
        if Booking.check_date_conflict(listing_id, start_date, end_date):
            raise serializers.ValidationError(
                "This listing is already booked for the selected dates."
            )

        return attrs

    def create(self, validated_data):
        listing_id = validated_data.pop("listing_id")
        listing = Listing.objects.get(id=listing_id)
        booking = Booking(
            listing=listing,
            renter=self.context["request"].user,
            **validated_data,
        )
        booking.calculate_total_price()
        booking.save()
        return booking


class BookingDetailSerializer(serializers.ModelSerializer):
    """Detailed booking view with listing summary and renter info."""

    renter = UserSummarySerializer(read_only=True)
    listing_title = serializers.CharField(source="listing.title", read_only=True)
    listing_slug = serializers.CharField(source="listing.slug", read_only=True)
    listing_city = serializers.CharField(source="listing.city", read_only=True)

    class Meta:
        model = Booking
        fields = [
            "id", "listing", "listing_title", "listing_slug", "listing_city",
            "renter", "start_date", "end_date", "total_price",
            "deposit_amount", "status", "note", "cancellation_reason",
            "created_at", "updated_at",
        ]


class BookingStatusUpdateSerializer(serializers.Serializer):
    """Update booking status with transition validation."""

    status = serializers.ChoiceField(
        choices=[
            "approved", "rejected", "paid", "active", "completed", "cancelled",
        ]
    )
    cancellation_reason = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        booking = self.context["booking"]
        new_status = attrs["status"]

        if not booking.can_transition_to(new_status):
            raise serializers.ValidationError(
                f"Cannot transition from '{booking.status}' to '{new_status}'."
            )

        # Require reason for rejection/cancellation
        if new_status in ("rejected", "cancelled") and not attrs.get("cancellation_reason"):
            raise serializers.ValidationError(
                {"cancellation_reason": "Reason is required for rejection/cancellation."}
            )

        return attrs
