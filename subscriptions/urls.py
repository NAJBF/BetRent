from django.urls import path

from .views import (
    CustomerPremiumStatusView,
    CustomerPremiumUpgradeView,
    CustomerPremiumVerifyView,
    LandlordPaymentVerifyView,
    MyLandlordSubscriptionView,
    PlanListView,
    SelectLandlordPlanView,
)

urlpatterns = [
    path("plans/", PlanListView.as_view(), name="plan-list"),
    path("landlord/select-plan/", SelectLandlordPlanView.as_view(), name="landlord-select-plan"),
    path("landlord/me/", MyLandlordSubscriptionView.as_view(), name="landlord-subscription-me"),
    path(
        "landlord/verify/<str:tx_ref>/",
        LandlordPaymentVerifyView.as_view(),
        name="landlord-payment-verify",
    ),
    path(
        "customer/premium/upgrade/",
        CustomerPremiumUpgradeView.as_view(),
        name="customer-premium-upgrade",
    ),
    path(
        "customer/premium/verify/<str:tx_ref>/",
        CustomerPremiumVerifyView.as_view(),
        name="customer-premium-verify",
    ),
    path(
        "customer/premium/status/",
        CustomerPremiumStatusView.as_view(),
        name="customer-premium-status",
    ),
]
