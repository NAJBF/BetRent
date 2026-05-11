from rest_framework import serializers
from django.db.models import Avg, Count
from .models import Review
from bookings.models import Booking


class ReviewCreateSerializer(serializers.ModelSerializer):
    """
    Create a review — validates that the reviewer has a completed booking
    for the listing. Prevents duplicate reviews.
    """

    listing_id = serializers.UUIDField(write_only=True)

    class Meta:
        model = Review
        fields = ["id", "listing_id", "rating", "comment", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate(self, attrs):
        user = self.context["request"].user
        listing_id = attrs["listing_id"]

        # Check for completed booking
        has_completed = Booking.objects.filter(
            listing_id=listing_id,
            renter=user,
            status="completed",
        ).exists()

        if not has_completed:
            raise serializers.ValidationError(
                "You can only review a listing after completing a rental."
            )

        # Check for duplicate review
        if Review.objects.filter(listing_id=listing_id, reviewer=user).exists():
            raise serializers.ValidationError(
                "You have already reviewed this listing."
            )

        return attrs

    def create(self, validated_data):
        listing_id = validated_data.pop("listing_id")
        from listings.models import Listing
        listing = Listing.objects.get(id=listing_id)
        return Review.objects.create(
            listing=listing,
            reviewer=self.context["request"].user,
            **validated_data,
        )


class ReviewSerializer(serializers.ModelSerializer):
    """Review display with reviewer info."""

    reviewer_name = serializers.CharField(source="reviewer.full_name", read_only=True)
    reviewer_avatar = serializers.URLField(source="reviewer.avatar_url", read_only=True)

    class Meta:
        model = Review
        fields = [
            "id", "rating", "comment", "reviewer_name",
            "reviewer_avatar", "created_at",
        ]


class ReviewStatsSerializer(serializers.Serializer):
    """Aggregate rating stats for a listing."""

    average_rating = serializers.FloatField()
    total_reviews = serializers.IntegerField()
