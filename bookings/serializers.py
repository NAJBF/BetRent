from rest_framework import serializers
from .models import Booking
from listings.models import Listing
from accounts.serializers import UserContactSerializer, UserSummarySerializer


APPROVED_STATUSES = ("approved", "paid", "active", "completed")


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

        user = self.context["request"].user
        if listing.is_premium_post and not user.can_view_premium_listings:
            raise serializers.ValidationError(
                "Premium listings require a premium customer subscription to book."
            )
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

        if listing.owner == user:
            raise serializers.ValidationError(
                "You cannot book your own listing."
            )

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
    """
    Detailed booking view with gated contact fields.

    - Landlord sees renter phone/email after approval.
    - Customer (renter) sees landlord phone/email after approval.
    """

    renter = serializers.SerializerMethodField()
    landlord = serializers.SerializerMethodField()
    listing_title = serializers.CharField(source="listing.title", read_only=True)
    listing_slug = serializers.CharField(source="listing.slug", read_only=True)
    listing_city = serializers.CharField(source="listing.city", read_only=True)
    contact_visible = serializers.SerializerMethodField()
    renter_contact_visible = serializers.SerializerMethodField()
    landlord_contact_visible = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = [
            "id", "listing", "listing_title", "listing_slug", "listing_city",
            "renter", "landlord",
            "contact_visible", "renter_contact_visible", "landlord_contact_visible",
            "start_date", "end_date", "total_price",
            "deposit_amount", "status", "note", "cancellation_reason",
            "created_at", "updated_at",
        ]

    def _request_user(self):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None
        return request.user

    def _is_approved(self, booking):
        return booking.status in APPROVED_STATUSES

    def _can_see_renter_contact(self, booking):
        user = self._request_user()
        if not user:
            return False
        if user.role == "admin":
            return True
        if booking.listing.owner == user and self._is_approved(booking):
            return True
        return False

    def _can_see_landlord_contact(self, booking):
        user = self._request_user()
        if not user:
            return False
        if user.role == "admin":
            return True
        if booking.listing.owner == user:
            return True
        if booking.renter == user and self._is_approved(booking):
            return True
        return False

    def get_renter_contact_visible(self, booking):
        return self._can_see_renter_contact(booking)

    def get_landlord_contact_visible(self, booking):
        return self._can_see_landlord_contact(booking)

    def get_contact_visible(self, booking):
        """True when the current user can see the other party's contact details."""
        user = self._request_user()
        if not user:
            return False
        if user.role == "admin":
            return True
        if booking.renter == user:
            return self._can_see_landlord_contact(booking)
        if booking.listing.owner == user:
            return self._can_see_renter_contact(booking)
        return False

    def get_renter(self, booking):
        if self._can_see_renter_contact(booking):
            return UserContactSerializer(booking.renter).data
        return UserSummarySerializer(booking.renter).data

    def get_landlord(self, booking):
        owner = booking.listing.owner
        if self._can_see_landlord_contact(booking):
            return UserContactSerializer(owner).data
        return UserSummarySerializer(owner).data


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

        if new_status in ("rejected", "cancelled") and not attrs.get("cancellation_reason"):
            raise serializers.ValidationError(
                {"cancellation_reason": "Reason is required for rejection/cancellation."}
            )

        if new_status == "approved":
            from subscriptions.services import check_landlord_can_approve
            landlord = booking.listing.owner
            allowed, error = check_landlord_can_approve(landlord)
            if not allowed:
                raise serializers.ValidationError(error)

        return attrs
