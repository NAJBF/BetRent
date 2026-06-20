from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin
from unfold.decorators import display

from .models import EmailOTP


@admin.register(EmailOTP)
class EmailOTPAdmin(ModelAdmin):
    list_display = [
        "email",
        "purpose",
        "display_code",
        "display_status",
        "expires_at",
        "created_at",
    ]
    list_filter = ["purpose", "is_used"]
    search_fields = ["email", "code"]
    readonly_fields = ["email", "purpose", "code", "expires_at", "is_used", "created_at", "updated_at"]
    ordering = ["-created_at"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @display(description="OTP Code")
    def display_code(self, obj):
        return format_html('<strong style="font-size:1.1em;letter-spacing:2px">{}</strong>', obj.code)

    @display(description="Status")
    def display_status(self, obj):
        if obj.is_used:
            return format_html('<span style="color:gray">Used</span>')
        if obj.is_expired:
            return format_html('<span style="color:red">Expired</span>')
        return format_html('<span style="color:green">Active</span>')
