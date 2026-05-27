from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema

from core.permissions import IsLandlord, IsOwnerOrAdmin
from core.pagination import BetRentPagination
from .models import Listing, ListingImage
from .serializers import (
    ListingListSerializer,
    ListingDetailSerializer,
    ListingCreateSerializer,
    ListingUpdateSerializer,
    ListingImageUploadSerializer,
)
from .filters import ListingFilter


class ListingListView(generics.ListAPIView):
    """GET /api/v1/listings/ — Public: search, filter, paginate listings."""

    serializer_class = ListingListSerializer
    permission_classes = [AllowAny]
    pagination_class = BetRentPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = ListingFilter

    def get_queryset(self):
        return (
            Listing.objects.filter(is_active=True)
            .select_related("category", "owner")
            .prefetch_related("images", "reviews", "bookings")
        )


class ListingDetailView(generics.RetrieveAPIView):
    """GET /api/v1/listings/{slug} — Public: view detail, auto-increment views."""

    serializer_class = ListingDetailSerializer
    permission_classes = [AllowAny]
    lookup_field = "slug"

    def get_queryset(self):
        return (
            Listing.objects.filter(is_active=True)
            .select_related("category", "owner")
            .prefetch_related("images", "reviews", "bookings")
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.increment_views()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class MyListingsView(generics.ListAPIView):
    """GET /api/v1/listings/my/listings — View own listings."""

    serializer_class = ListingListSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = BetRentPagination

    def get_queryset(self):
        return (
            Listing.objects.filter(owner=self.request.user)
            .select_related("category", "owner")
            .prefetch_related("images", "reviews", "bookings")
        )


class ListingCreateView(generics.CreateAPIView):
    """POST /api/v1/listings/ — Landlord: create a listing."""

    @extend_schema(responses={201: ListingDetailSerializer})
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    serializer_class = ListingCreateSerializer
    permission_classes = [IsLandlord]


class ListingUpdateView(generics.UpdateAPIView):
    """PUT /api/v1/listings/{id} — Owner: update listing fields."""

    @extend_schema(responses={200: ListingDetailSerializer})
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)

    serializer_class = ListingUpdateSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    queryset = Listing.objects.all()
    lookup_field = "pk"
    lookup_url_kwarg = "listing_id"


class ListingDeleteView(generics.DestroyAPIView):
    """DELETE /api/v1/listings/{id} — Owner: soft-delete listing."""

    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    queryset = Listing.objects.all()
    lookup_field = "pk"
    lookup_url_kwarg = "listing_id"

    def perform_destroy(self, instance):
        # Soft delete — deactivate instead of removing
        instance.is_active = False
        instance.save(update_fields=["is_active"])


class ListingImageCreateView(generics.CreateAPIView):
    """
    POST /api/v1/listings/{id}/images — Owner: add image to listing.

    Accepts multipart/form-data with an 'image' file field (for Expo / mobile)
    OR a JSON body with 'image_url' string (backward compatible).
    """

    serializer_class = ListingImageUploadSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def perform_create(self, serializer):
        listing = Listing.objects.get(pk=self.kwargs["listing_id"])
        # Verify ownership
        if listing.owner != self.request.user and self.request.user.role != "admin":
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You can only add images to your own listings.")
        serializer.save(listing=listing)
