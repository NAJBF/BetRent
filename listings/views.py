from datetime import timedelta

from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.views import APIView
from rest_framework.exceptions import NotFound, PermissionDenied
from django.conf import settings
from django.db import models
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema

from core.permissions import IsLandlord, IsOwnerOrAdmin
from core.pagination import BetRentPagination
from .models import Listing, ListingImage, PromotionPayment
from .serializers import (
    ListingListSerializer,
    ListingDetailSerializer,
    ListingCreateSerializer,
    ListingUpdateSerializer,
    ListingImageUploadSerializer,
    PromotionRequestSerializer,
    PromotionPaymentSerializer,
)
from .filters import ListingFilter
from payments.services import ChapaService


# ---------------------------------------------------------------------------
# Promotion pricing table (fallback if not in settings)
# ---------------------------------------------------------------------------
PROMOTION_PRICING = getattr(settings, "PROMOTION_PRICING", {7: 200, 14: 350, 30: 600})


def _user_can_view_premium(user):
    """Check if user can view premium listings."""
    if not user or not user.is_authenticated:
        return False
    return user.can_view_premium_listings


def _filter_premium_listings(queryset, user):
    """Hide premium posts from non-premium users (owner/admin always see their own)."""
    if _user_can_view_premium(user):
        return queryset
    if user and user.is_authenticated and user.is_landlord:
        # Landlords see all listings except premium ones they don't own
        return queryset.filter(
            models.Q(is_premium_post=False) | models.Q(owner=user)
        )
    return queryset.filter(is_premium_post=False)


class ListingListView(generics.ListAPIView):
    """GET /api/v1/listings/ — Public: search, filter, paginate listings."""

    serializer_class = ListingListSerializer
    permission_classes = [AllowAny]
    pagination_class = BetRentPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = ListingFilter

    def get_queryset(self):
        qs = (
            Listing.objects.filter(is_active=True)
            .select_related("category", "owner")
            .prefetch_related("images", "reviews", "bookings")
            .order_by("-is_featured", "-created_at")
        )
        return _filter_premium_listings(qs, self.request.user)


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

        # Block premium listing access for non-premium customers
        if instance.is_premium_post:
            user = request.user
            is_owner = user.is_authenticated and instance.owner == user
            is_admin = user.is_authenticated and user.role == "admin"
            if not is_owner and not is_admin and not _user_can_view_premium(user):
                return Response(
                    {
                        "detail": "This is a premium listing. Upgrade to a premium customer subscription to view.",
                        "requires_premium": True,
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

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
    """POST /api/v1/listings/create/ — Landlord: create a listing."""

    @extend_schema(responses={201: ListingDetailSerializer})
    def post(self, request, *args, **kwargs):
        if not request.user.can_post_listings:
            return Response(
                {
                    "detail": "Posting is not allowed. Verify email and complete payment first.",
                    "account_status": request.user.account_status,
                },
                status=status.HTTP_403_FORBIDDEN,
            )
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


# ---------------------------------------------------------------------------
# Featured Listing Promotion Views
# ---------------------------------------------------------------------------


class ListingPromoteView(APIView):
    """
    POST /api/v1/listings/{listing_id}/promote/
    Landlord: initiate a Chapa payment to promote a listing as featured.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=PromotionRequestSerializer,
        responses={201: PromotionPaymentSerializer},
    )
    def post(self, request, listing_id):
        # Fetch listing
        try:
            listing = Listing.objects.get(pk=listing_id)
        except Listing.DoesNotExist:
            raise NotFound("Listing not found.")

        # Only the owner (landlord) can promote
        if listing.owner != request.user and request.user.role != "admin":
            raise PermissionDenied("Only the listing owner can promote this listing.")

        # Cannot promote inactive listings
        if not listing.is_active:
            return Response(
                {"detail": "Cannot promote an inactive or deleted listing."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate duration
        serializer = PromotionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        duration_days = int(serializer.validated_data["duration_days"])

        # Lookup price
        amount = PROMOTION_PRICING.get(duration_days)
        if amount is None:
            return Response(
                {"detail": f"Invalid promotion duration: {duration_days} days."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Create promotion payment record
        promo_payment = PromotionPayment.objects.create(
            listing=listing,
            payer=request.user,
            duration_days=duration_days,
            amount=amount,
        )

        # Initiate Chapa payment
        chapa_result = ChapaService.initiate_payment(
            amount=float(amount),
            tx_ref=promo_payment.transaction_ref,
            email=request.user.email,
            first_name=request.user.full_name.split()[0] if request.user.full_name else "User",
        )
        promo_payment.checkout_url = chapa_result.get("checkout_url", "")
        promo_payment.save(update_fields=["checkout_url"])

        return Response(
            PromotionPaymentSerializer(promo_payment).data,
            status=status.HTTP_201_CREATED,
        )


class PromotionVerifyView(APIView):
    """
    GET /api/v1/listings/promotions/verify/{tx_ref}/
    Verify a promotion payment and activate the featured listing.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: PromotionPaymentSerializer})
    def get(self, request, tx_ref):
        try:
            promo_payment = PromotionPayment.objects.select_related("listing").get(
                transaction_ref=tx_ref
            )
        except PromotionPayment.DoesNotExist:
            raise NotFound("Promotion payment not found.")

        # Verify with Chapa if still pending
        if promo_payment.status == "pending":
            result = ChapaService.verify_payment(tx_ref)
            if result["status"] == "success":
                promo_payment.status = "completed"
                promo_payment.save(update_fields=["status"])

                # Activate featured listing
                listing = promo_payment.listing
                listing.is_featured = True
                listing.featured_until = (
                    timezone.now() + timedelta(days=promo_payment.duration_days)
                )
                listing.save(update_fields=["is_featured", "featured_until"])
            else:
                promo_payment.status = "failed"
                promo_payment.save(update_fields=["status"])

        return Response(PromotionPaymentSerializer(promo_payment).data)


class PromotionWebhookView(APIView):
    """
    POST /api/v1/listings/promotions/webhook/chapa/
    Chapa webhook callback for promotion payments. No auth required.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        tx_ref = request.data.get("tx_ref")
        webhook_status = request.data.get("status")

        if not tx_ref or not webhook_status:
            return Response(
                {"detail": "tx_ref and status are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            promo_payment = PromotionPayment.objects.select_related("listing").get(
                transaction_ref=tx_ref
            )
        except PromotionPayment.DoesNotExist:
            raise NotFound("Promotion payment not found.")

        if webhook_status == "success" and promo_payment.status == "pending":
            promo_payment.status = "completed"
            promo_payment.save(update_fields=["status"])

            # Activate featured listing
            listing = promo_payment.listing
            listing.is_featured = True
            listing.featured_until = (
                timezone.now() + timedelta(days=promo_payment.duration_days)
            )
            listing.save(update_fields=["is_featured", "featured_until"])
        elif webhook_status != "success":
            promo_payment.status = "failed"
            promo_payment.save(update_fields=["status"])

        return Response({"status": "received"}, status=status.HTTP_200_OK)

