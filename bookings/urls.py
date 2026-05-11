from django.urls import path
from .views import (
    BookingCreateView,
    MyRentalsView,
    MyBookingRequestsView,
    BookingDetailView,
    BookingStatusUpdateView,
)

urlpatterns = [
    path("", BookingCreateView.as_view(), name="booking-create"),
    path("my/rentals/", MyRentalsView.as_view(), name="my-rentals"),
    path("my/requests/", MyBookingRequestsView.as_view(), name="my-booking-requests"),
    path("<uuid:booking_id>/", BookingDetailView.as_view(), name="booking-detail"),
    path("<uuid:booking_id>/status/", BookingStatusUpdateView.as_view(), name="booking-status-update"),
]
