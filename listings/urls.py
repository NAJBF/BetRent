from django.urls import path
from .views import (
    ListingListView,
    ListingDetailView,
    MyListingsView,
    ListingCreateView,
    ListingUpdateView,
    ListingDeleteView,
    ListingImageCreateView,
)

urlpatterns = [
    path("", ListingListView.as_view(), name="listing-list"),
    path("create/", ListingCreateView.as_view(), name="listing-create"),
    path("my/listings/", MyListingsView.as_view(), name="my-listings"),
    path("<uuid:listing_id>/update/", ListingUpdateView.as_view(), name="listing-update"),
    path("<uuid:listing_id>/delete/", ListingDeleteView.as_view(), name="listing-delete"),
    path("<uuid:listing_id>/images/", ListingImageCreateView.as_view(), name="listing-image-create"),
    path("<slug:slug>/", ListingDetailView.as_view(), name="listing-detail"),
]
