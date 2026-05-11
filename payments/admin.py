from django.contrib import admin
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
    list_editable = ["status"] # Allows one-click status change in the list
    list_filter = ["status", "method"]
    search_fields = ["transaction_ref", "booking__listing__title"]
    readonly_fields = ["transaction_ref", "created_at", "updated_at"]
    ordering = ["-created_at"]
