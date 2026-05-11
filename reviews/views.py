from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema
from django.db.models import Avg, Count

from core.permissions import IsOwnerOrAdmin
from core.pagination import BetRentPagination
from .models import Review
from .serializers import ReviewCreateSerializer, ReviewSerializer, ReviewStatsSerializer


class ReviewCreateView(generics.CreateAPIView):
    """POST /api/v1/reviews/ — Submit a review (requires completed booking)."""

    @extend_schema(responses={201: ReviewSerializer})
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    serializer_class = ReviewCreateSerializer
    permission_classes = [IsAuthenticated]


class ListingReviewsView(generics.ListAPIView):
    """GET /api/v1/reviews/listing/{listing_id} — All reviews for a listing (public)."""

    serializer_class = ReviewSerializer
    permission_classes = [AllowAny]
    pagination_class = BetRentPagination

    def get_queryset(self):
        listing_id = self.kwargs["listing_id"]
        return Review.objects.filter(listing_id=listing_id).select_related("reviewer")


class ListingReviewStatsView(APIView):
    """GET /api/v1/reviews/listing/{listing_id}/stats — Rating stats (public)."""

    permission_classes = [AllowAny]

    @extend_schema(responses={200: ReviewStatsSerializer})
    def get(self, request, listing_id):
        stats = Review.objects.filter(listing_id=listing_id).aggregate(
            average_rating=Avg("rating"),
            total_reviews=Count("id"),
        )
        stats["average_rating"] = (
            round(stats["average_rating"], 1) if stats["average_rating"] else 0
        )
        return Response(ReviewStatsSerializer(stats).data)


class ReviewDeleteView(generics.DestroyAPIView):
    """DELETE /api/v1/reviews/{id} — Delete own review."""

    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    queryset = Review.objects.all()
    lookup_field = "pk"
    lookup_url_kwarg = "review_id"

    def get_object(self):
        obj = super().get_object()
        if obj.reviewer != self.request.user and self.request.user.role != "admin":
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You can only delete your own reviews.")
        return obj
