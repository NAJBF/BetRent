from django.urls import path
from .views import (
    PaymentInitiateView,
    PaymentVerifyView,
    BookingPaymentView,
    ChapaWebhookView,
    PaymentManualUpdateView,
    ExternalPaymentRecordView,
    ExternalPaymentVerifyView,
)

urlpatterns = [
    path("initiate/", PaymentInitiateView.as_view(), name="payment-initiate"),
    path("verify/<str:tx_ref>/", PaymentVerifyView.as_view(), name="payment-verify"),
    path("booking/<uuid:booking_id>/", BookingPaymentView.as_view(), name="booking-payment"),
    path("webhook/chapa/", ChapaWebhookView.as_view(), name="chapa-webhook"),
    path("<uuid:payment_id>/manual-update/", PaymentManualUpdateView.as_view(), name="payment-manual-update"),
    path("external/record/", ExternalPaymentRecordView.as_view(), name="external-payment-record"),
    path("external/verify/", ExternalPaymentVerifyView.as_view(), name="external-payment-verify"),
]
