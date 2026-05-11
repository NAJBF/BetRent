from django.urls import path
from .views import (
    ReviewCreateView,
    ListingReviewsView,
    ListingReviewStatsView,
    ReviewDeleteView,
)

urlpatterns = [
    path("", ReviewCreateView.as_view(), name="review-create"),
    path("listing/<uuid:listing_id>/", ListingReviewsView.as_view(), name="listing-reviews"),
    path("listing/<uuid:listing_id>/stats/", ListingReviewStatsView.as_view(), name="listing-review-stats"),
    path("<uuid:review_id>/", ReviewDeleteView.as_view(), name="review-delete"),
]
