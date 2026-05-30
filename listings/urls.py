from django.urls import path
from .views import (
    ListingListView,
    ListingDetailView,
    MyListingsView,
    ListingCreateView,
    ListingUpdateView,
    ListingDeleteView,
    ListingImageCreateView,
    ListingPromoteView,
    PromotionVerifyView,
    PromotionWebhookView,
)

urlpatterns = [
    path("", ListingListView.as_view(), name="listing-list"),
    path("create/", ListingCreateView.as_view(), name="listing-create"),
    path("my/listings/", MyListingsView.as_view(), name="my-listings"),
    # Promotion endpoints
    path("promotions/verify/<str:tx_ref>/", PromotionVerifyView.as_view(), name="promotion-verify"),
    path("promotions/webhook/chapa/", PromotionWebhookView.as_view(), name="promotion-webhook"),
    path("<uuid:listing_id>/update/", ListingUpdateView.as_view(), name="listing-update"),
    path("<uuid:listing_id>/delete/", ListingDeleteView.as_view(), name="listing-delete"),
    path("<uuid:listing_id>/images/", ListingImageCreateView.as_view(), name="listing-image-create"),
    path("<uuid:listing_id>/promote/", ListingPromoteView.as_view(), name="listing-promote"),
    path("<slug:slug>/", ListingDetailView.as_view(), name="listing-detail"),
]

