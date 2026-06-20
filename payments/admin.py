from django.contrib import admin
from django.db.models import Sum
from django.urls import path
from django.shortcuts import render
from unfold.admin import ModelAdmin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(ModelAdmin):
    list_display = [
        "transaction_ref",
        "booking",
        "amount",
        "method",
        "status",
        "created_at",
    ]
    list_editable = ["status"]
    list_filter = ["status", "method"]
    search_fields = ["transaction_ref", "booking__listing__title"]
    readonly_fields = ["transaction_ref", "created_at", "updated_at"]
    ordering = ["-created_at"]

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "income-dashboard/",
                self.admin_site.admin_view(self.income_dashboard_view),
                name="betrent_income_dashboard",
            ),
        ]
        return custom + urls

    def income_dashboard_view(self, request):
        from listings.models import PromotionPayment
        from subscriptions.models import CustomerPremiumSubscription, LandlordSubscription

        booking_income = Payment.objects.filter(status="completed").aggregate(
            total=Sum("amount")
        )["total"] or 0

        promotion_income = PromotionPayment.objects.filter(status="completed").aggregate(
            total=Sum("amount")
        )["total"] or 0

        landlord_sub_income = LandlordSubscription.objects.filter(
            payment_status="completed"
        ).aggregate(total=Sum("amount"))["total"] or 0

        customer_premium_income = CustomerPremiumSubscription.objects.filter(
            payment_status="completed"
        ).aggregate(total=Sum("amount"))["total"] or 0

        total_income = (
            booking_income + promotion_income + landlord_sub_income + customer_premium_income
        )

        recent_payments = []

        for p in Payment.objects.filter(status="completed").select_related(
            "booking__renter"
        ).order_by("-created_at")[:10]:
            recent_payments.append(
                {
                    "type": "Booking Payment",
                    "ref": p.transaction_ref,
                    "amount": p.amount,
                    "date": p.created_at,
                    "user": p.booking.renter.email,
                }
            )

        for p in PromotionPayment.objects.filter(status="completed").select_related(
            "payer"
        ).order_by("-created_at")[:10]:
            recent_payments.append(
                {
                    "type": "Listing Promotion",
                    "ref": p.transaction_ref,
                    "amount": p.amount,
                    "date": p.created_at,
                    "user": p.payer.email,
                }
            )

        for s in LandlordSubscription.objects.filter(
            payment_status="completed"
        ).select_related("user").order_by("-created_at")[:10]:
            recent_payments.append(
                {
                    "type": "Landlord Subscription",
                    "ref": s.transaction_ref,
                    "amount": s.amount,
                    "date": s.created_at,
                    "user": s.user.email,
                }
            )

        for s in CustomerPremiumSubscription.objects.filter(
            payment_status="completed"
        ).select_related("user").order_by("-created_at")[:10]:
            recent_payments.append(
                {
                    "type": "Customer Premium",
                    "ref": s.transaction_ref,
                    "amount": s.amount,
                    "date": s.created_at,
                    "user": s.user.email,
                }
            )

        recent_payments.sort(key=lambda x: x["date"], reverse=True)

        context = {
            **self.admin_site.each_context(request),
            "title": "Income Dashboard",
            "total_income": total_income,
            "booking_income": booking_income,
            "promotion_income": promotion_income,
            "landlord_sub_income": landlord_sub_income,
            "customer_premium_income": customer_premium_income,
            "recent_payments": recent_payments[:20],
        }
        return render(request, "admin/income_dashboard.html", context)
