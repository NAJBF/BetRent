from rest_framework import serializers
from django.db.models import Avg, Count
from .models import Listing, ListingImage
from accounts.serializers import UserSummarySerializer
from categories.serializers import CategoryChildSerializer


class ListingImageSerializer(serializers.ModelSerializer):
    """Read serializer — returns a unified image_url regardless of storage method."""

    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ListingImage
        fields = ["id", "image_url", "is_primary", "sort_order"]
        read_only_fields = ["id"]

    def get_image_url(self, obj):
        """Prefer the uploaded file URL; fall back to the legacy URL string."""
        if obj.image:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return obj.image_url or None


class ListingImageUploadSerializer(serializers.ModelSerializer):
    """
    Create serializer — accepts either:
      • image  (file upload via multipart/form-data)  ← Expo / mobile
      • image_url  (URL string)                       ← backward compat
    At least one must be provided.
    """

    image = serializers.ImageField(required=False, allow_null=True)
    image_url = serializers.URLField(required=False, allow_blank=True, default="")

    class Meta:
        model = ListingImage
        fields = ["id", "image", "image_url", "is_primary", "sort_order"]
        read_only_fields = ["id"]

    def validate(self, attrs):
        image = attrs.get("image")
        image_url = attrs.get("image_url", "")
        if not image and not image_url:
            raise serializers.ValidationError(
                "Either 'image' (file) or 'image_url' (URL) must be provided."
            )
        return attrs


class ListingListSerializer(serializers.ModelSerializer):
    """Summary view for listing search results."""

    primary_image = serializers.SerializerMethodField()
    category_name = serializers.CharField(source="category.name", read_only=True, default=None)
    owner_name = serializers.CharField(source="owner.full_name", read_only=True)
    average_rating = serializers.SerializerMethodField()
    total_reviews = serializers.SerializerMethodField()
    is_available = serializers.SerializerMethodField()

    class Meta:
        model = Listing
        fields = [
            "id", "title", "slug", "price_per_day", "price_per_week",
            "price_per_month", "deposit_amount", "condition", "city",
            "views_count", "primary_image", "category_name", "owner_name",
            "average_rating", "total_reviews", "is_available", "created_at",
        ]

    def get_primary_image(self, obj):
        img = obj.images.filter(is_primary=True).first()
        if not img:
            img = obj.images.first()
        if not img:
            return None
        # Prefer uploaded file over legacy URL
        if img.image:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(img.image.url)
            return img.image.url
        return img.image_url or None

    def get_average_rating(self, obj):
        result = obj.reviews.aggregate(avg=Avg("rating"))
        return round(result["avg"], 1) if result["avg"] else None

    def get_total_reviews(self, obj):
        return obj.reviews.count()

    def get_is_available(self, obj):
        """Property is unavailable if any booking is approved, paid, or active."""
        return not obj.bookings.filter(
            status__in=["approved", "paid", "active"]
        ).exists()


class ListingDetailSerializer(serializers.ModelSerializer):
    """Full detail view with all images, owner info, and review stats."""

    images = ListingImageSerializer(many=True, read_only=True)
    owner = UserSummarySerializer(read_only=True)
    category = CategoryChildSerializer(read_only=True)
    average_rating = serializers.SerializerMethodField()
    total_reviews = serializers.SerializerMethodField()
    is_available = serializers.SerializerMethodField()

    class Meta:
        model = Listing
        fields = [
            "id", "title", "slug", "description", "price_per_day",
            "price_per_week", "price_per_month", "deposit_amount",
            "condition", "city", "address", "views_count", "is_active",
            "is_available", "category", "owner", "images",
            "average_rating", "total_reviews",
            "created_at", "updated_at",
        ]

    def get_average_rating(self, obj):
        result = obj.reviews.aggregate(avg=Avg("rating"))
        return round(result["avg"], 1) if result["avg"] else None

    def get_total_reviews(self, obj):
        return obj.reviews.count()

    def get_is_available(self, obj):
        """Property is unavailable if any booking is approved, paid, or active."""
        return not obj.bookings.filter(
            status__in=["approved", "paid", "active"]
        ).exists()


class ListingCreateSerializer(serializers.ModelSerializer):
    """Create a new listing (landlord only)."""

    category_id = serializers.UUIDField(write_only=True)

    class Meta:
        model = Listing
        fields = [
            "id", "title", "description", "price_per_day", "price_per_week",
            "price_per_month", "deposit_amount", "condition", "city",
            "address", "category_id", "slug",
        ]
        read_only_fields = ["id", "slug"]

    def validate_category_id(self, value):
        from categories.models import Category
        if not Category.objects.filter(id=value).exists():
            raise serializers.ValidationError("Category not found.")
        return value

    def create(self, validated_data):
        from categories.models import Category
        category_id = validated_data.pop("category_id")
        validated_data["category"] = Category.objects.get(id=category_id)
        validated_data["owner"] = self.context["request"].user
        return super().create(validated_data)


class ListingUpdateSerializer(serializers.ModelSerializer):
    """Update listing fields (owner only)."""

    class Meta:
        model = Listing
        fields = [
            "title", "description", "price_per_day", "price_per_week",
            "price_per_month", "deposit_amount", "condition", "city", "address",
        ]
