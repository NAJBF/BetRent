from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from core.permissions import IsAdminRole
from .models import Category
from .serializers import (
    CategoryTreeSerializer,
    CategoryCreateSerializer,
    CategoryUpdateSerializer,
)


class CategoryListView(generics.ListAPIView):
    """GET /api/v1/categories/ — Public: full category tree."""

    serializer_class = CategoryTreeSerializer
    permission_classes = [AllowAny]
    pagination_class = None  # Return full tree, no pagination

    def get_queryset(self):
        # Only return root categories; children are nested via serializer
        return Category.objects.filter(parent__isnull=True).prefetch_related("children")


class CategoryDetailView(generics.RetrieveAPIView):
    """GET /api/v1/categories/{slug} — Public: single category by slug."""

    serializer_class = CategoryTreeSerializer
    permission_classes = [AllowAny]
    lookup_field = "slug"

    def get_queryset(self):
        return Category.objects.prefetch_related("children")


class CategoryCreateView(generics.CreateAPIView):
    """POST /api/v1/categories/ — Admin: create category."""

    serializer_class = CategoryCreateSerializer
    permission_classes = [IsAdminRole]


class CategoryUpdateView(generics.UpdateAPIView):
    """PUT /api/v1/categories/{id} — Admin: update category."""

    serializer_class = CategoryUpdateSerializer
    permission_classes = [IsAdminRole]
    queryset = Category.objects.all()
    lookup_field = "pk"
    lookup_url_kwarg = "category_id"


class CategoryDeleteView(generics.DestroyAPIView):
    """DELETE /api/v1/categories/{id} — Admin: delete category."""

    permission_classes = [IsAdminRole]
    queryset = Category.objects.all()
    lookup_field = "pk"
    lookup_url_kwarg = "category_id"
