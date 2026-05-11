from rest_framework import serializers
from .models import Category


class CategoryChildSerializer(serializers.ModelSerializer):
    """Serializer for child categories (no recursion beyond 1 level for safety)."""

    class Meta:
        model = Category
        fields = ["id", "name", "slug", "description", "icon"]


class CategoryTreeSerializer(serializers.ModelSerializer):
    """
    Recursive category tree serializer.
    Returns nested children for building category navigation.
    """

    children = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ["id", "name", "slug", "description", "icon", "children"]

    def get_children(self, obj):
        children = obj.children.all()
        return CategoryTreeSerializer(children, many=True).data


class CategoryCreateSerializer(serializers.ModelSerializer):
    """Create a new category (admin only)."""

    parent_id = serializers.UUIDField(required=False, allow_null=True)

    class Meta:
        model = Category
        fields = ["id", "name", "description", "icon", "parent_id", "slug"]
        read_only_fields = ["id", "slug"]

    def validate_parent_id(self, value):
        if value:
            try:
                Category.objects.get(id=value)
            except Category.DoesNotExist:
                raise serializers.ValidationError("Parent category not found.")
        return value

    def create(self, validated_data):
        parent_id = validated_data.pop("parent_id", None)
        if parent_id:
            validated_data["parent"] = Category.objects.get(id=parent_id)
        return super().create(validated_data)


class CategoryUpdateSerializer(serializers.ModelSerializer):
    """Update an existing category (admin only)."""

    class Meta:
        model = Category
        fields = ["name", "description", "icon"]
