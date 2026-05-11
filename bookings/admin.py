from django.contrib import admin
from unfold.admin import ModelAdmin
from unfold.decorators import display
from .models import Booking


@admin.register(Booking)
class BookingAdmin(ModelAdmin):
    list_display = [
        "display_header",
        "display_duration",
        "display_total_price",
        "display_status",
        "created_at",
    ]
    list_filter = ["status", "start_date"]
    search_fields = ["listing__title", "renter__email"]
    readonly_fields = ["total_price", "deposit_amount", "created_at", "updated_at"]
    ordering = ["-created_at"]
    autocomplete_fields = ["listing", "renter"]

    @display(description="Booking", header=True)
    def display_header(self, instance):
        return [
            f"Booking #{instance.id.hex[:8].upper()}",
            f"{instance.listing.title} for {instance.renter.full_name or instance.renter.email}",
        ]

    @display(description="Duration")
    def display_duration(self, instance):
        return f"{instance.start_date} to {instance.end_date}"

    @display(description="Total Revenue", label="success")
    def display_total_price(self, instance):
        return f"{instance.total_price:,.2f} ETB"

    @display(description="Status", label={
        Booking.Status.PENDING: "warning",
        Booking.Status.APPROVED: "info",
        Booking.Status.PAID: "success",
        Booking.Status.ACTIVE: "success",
        Booking.Status.COMPLETED: "success",
        Booking.Status.REJECTED: "danger",
        Booking.Status.CANCELLED: "danger",
    })
    def display_status(self, instance):
        return instance.status

    fieldsets = (
        (None, {"fields": ("listing", "renter", "status")}),
        ("Schedule", {
            "classes": ["tab"],
            "fields": ("start_date", "end_date")
        }),
        ("Financials", {
            "classes": ["tab"],
            "fields": ("total_price", "deposit_amount")
        }),
        ("Notes & Feedback", {
            "classes": ["tab"],
            "fields": ("note", "cancellation_reason")
        }),
    )
