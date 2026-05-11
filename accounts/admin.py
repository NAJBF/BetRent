from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from unfold.admin import ModelAdmin
from unfold.decorators import display
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    list_display = [
        "display_header",
        "display_role",
        "city",
        "display_status",
        "date_joined"
    ]
    list_filter = ["role", "is_active", "city", "is_staff"]
    search_fields = ["email", "full_name", "phone"]
    ordering = ["-date_joined"]

    # Unfold custom display for the header (email + avatar)
    @display(description="User", header=True)
    def display_header(self, instance):
        return [
            instance.full_name or "No Name",
            instance.email,
            instance.avatar_url or None, # This will show the avatar if available
        ]

    @display(description="Role", label={
        User.Role.ADMIN: "danger",
        User.Role.LANDLORD: "info",
        User.Role.CUSTOMER: "success",
    })
    def display_role(self, instance):
        return instance.role

    @display(description="Status", boolean=True)
    def display_status(self, instance):
        return instance.is_active

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal Profile", {
            "classes": ["tab"],
            "fields": ("full_name", "phone", "city", "bio", "avatar_url")
        }),
        ("Role & Permissions", {
            "classes": ["tab"],
            "fields": ("role", "is_active", "is_staff", "is_superuser")
        }),
        ("Activity Metadata", {
            "classes": ["tab"],
            "fields": ("last_login", "date_joined")
        }),
    )
