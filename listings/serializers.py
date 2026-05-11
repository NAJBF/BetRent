from rest_framework import serializers
from django.db.models import Avg, Count
from .models import Listing, ListingImage
from accounts.serializers import UserSummarySerializer
from categories.serializers import CategoryChildSerializer


class ListingImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ListingImage
        fields = ["id", "image_url", "is_primary", "sort_order"]
        read_only_fields = ["id"]


class ListingImageCreateSerializer(serializers.ModelSerializer):
    """Add an image URL to a listing."""

    class Meta:
        model = ListingImage
        fields = ["id", "image_url", "is_primary", "sort_order"]
        read_only_fields = ["id"]


class ListingListSerializer(serializers.ModelSerializer):
    """Summary view for listing search results."""

    primary_image = serializers.SerializerMethodField()
    category_name = serializers.CharField(source="category.name", read_only=True, default=None)
    owner_name = serializers.CharField(source="owner.full_name", read_only=True)
    average_rating = serializers.SerializerMethodField()
    total_reviews = serializers.SerializerMethodField()

    class Meta:
        model = Listing
        fields = [
            "id", "title", "slug", "price_per_day", "price_per_week",
            "price_per_month", "deposit_amount", "condition", "city",
            "views_count", "primary_image", "category_name", "owner_name",
            "average_rating", "total_reviews", "created_at",
        ]

    def get_primary_image(self, obj):
        img = obj.images.filter(is_primary=True).first()
        if not img:
            img = obj.images.first()
        return img.image_url if img else None

    def get_average_rating(self, obj):
        result = obj.reviews.aggregate(avg=Avg("rating"))
        return round(result["avg"], 1) if result["avg"] else None

    def get_total_reviews(self, obj):
        return obj.reviews.count()


class ListingDetailSerializer(serializers.ModelSerializer):
    """Full detail view with all images, owner info, and review stats."""

    images = ListingImageSerializer(many=True, read_only=True)
    owner = UserSummarySerializer(read_only=True)
    category = CategoryChildSerializer(read_only=True)
    average_rating = serializers.SerializerMethodField()
    total_reviews = serializers.SerializerMethodField()

    class Meta:
        model = Listing
        fields = [
            "id", "title", "slug", "description", "price_per_day",
            "price_per_week", "price_per_month", "deposit_amount",
            "condition", "city", "address", "views_count", "is_active",
            "category", "owner", "images", "average_rating", "total_reviews",
            "created_at", "updated_at",
        ]

    def get_average_rating(self, obj):
        result = obj.reviews.aggregate(avg=Avg("rating"))
        return round(result["avg"], 1) if result["avg"] else None

    def get_total_reviews(self, obj):
        return obj.reviews.count()


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
