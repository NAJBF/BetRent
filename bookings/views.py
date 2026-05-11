from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied, NotFound

from core.pagination import BetRentPagination
from .models import Booking
from .serializers import (
    BookingCreateSerializer,
    BookingDetailSerializer,
    BookingStatusUpdateSerializer,
)


class BookingCreateView(generics.CreateAPIView):
    """POST /api/v1/bookings/ — Create a booking request (auto-calculates price)."""

    serializer_class = BookingCreateSerializer
    permission_classes = [IsAuthenticated]


class MyRentalsView(generics.ListAPIView):
    """GET /api/v1/bookings/my/rentals — My bookings as a renter."""

    serializer_class = BookingDetailSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = BetRentPagination

    def get_queryset(self):
        return (
            Booking.objects.filter(renter=self.request.user)
            .select_related("listing", "renter")
        )


class MyBookingRequestsView(generics.ListAPIView):
    """GET /api/v1/bookings/my/requests — Booking requests for my listings (landlord)."""

    serializer_class = BookingDetailSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = BetRentPagination

    def get_queryset(self):
        return (
            Booking.objects.filter(listing__owner=self.request.user)
            .select_related("listing", "renter")
        )


class BookingDetailView(generics.RetrieveAPIView):
    """GET /api/v1/bookings/{id} — View booking detail (renter or listing owner)."""

    serializer_class = BookingDetailSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "pk"
    lookup_url_kwarg = "booking_id"

    def get_queryset(self):
        user = self.request.user
        return Booking.objects.filter(
            models__isnull=False  # dummy filter, overridden below
        ).select_related("listing", "renter")

    def get_object(self):
        try:
            booking = (
                Booking.objects.select_related("listing", "listing__owner", "renter")
                .get(pk=self.kwargs["booking_id"])
            )
        except Booking.DoesNotExist:
            raise NotFound("Booking not found.")

        user = self.request.user
        if booking.renter != user and booking.listing.owner != user and user.role != "admin":
            raise PermissionDenied("You do not have access to this booking.")
        return booking


class BookingStatusUpdateView(APIView):
    """PUT /api/v1/bookings/{id}/status — Update booking status."""

    permission_classes = [IsAuthenticated]

    def put(self, request, booking_id):
        try:
            booking = (
                Booking.objects.select_related("listing", "listing__owner", "renter")
                .get(pk=booking_id)
            )
        except Booking.DoesNotExist:
            raise NotFound("Booking not found.")

        user = request.user
        new_status = request.data.get("status")

        # Permission checks based on status transition
        if new_status in ("approved", "rejected"):
            # Only the listing owner can approve/reject
            if booking.listing.owner != user and user.role != "admin":
                raise PermissionDenied("Only the listing owner can approve or reject.")
        elif new_status == "cancelled":
            # Both renter and owner can cancel
            if booking.renter != user and booking.listing.owner != user and user.role != "admin":
                raise PermissionDenied("You do not have access to this booking.")
        elif new_status in ("active", "completed"):
            # Only the listing owner can mark active/completed
            if booking.listing.owner != user and user.role != "admin":
                raise PermissionDenied("Only the listing owner can update this status.")
        else:
            raise PermissionDenied("Invalid status update.")

        serializer = BookingStatusUpdateSerializer(
            data=request.data, context={"booking": booking}
        )
        serializer.is_valid(raise_exception=True)

        booking.status = serializer.validated_data["status"]
        if serializer.validated_data.get("cancellation_reason"):
            booking.cancellation_reason = serializer.validated_data["cancellation_reason"]
        booking.save(update_fields=["status", "cancellation_reason", "updated_at"])

        return Response(BookingDetailSerializer(booking).data, status=status.HTTP_200_OK)
