from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import display
from .models import Listing, ListingImage


class ListingImageInline(TabularInline):
    model = ListingImage
    extra = 1
    fields = ["image_url", "is_primary", "sort_order"]


@admin.register(Listing)
class ListingAdmin(ModelAdmin):
    list_display = [
        "display_header",
        "display_category",
        "city",
        "display_price",
        "display_condition",
        "display_status",
        "views_count",
    ]
    list_filter = ["is_active", "condition", "city", "category"]
    search_fields = ["title", "description", "city", "owner__email"]
    autocomplete_fields = ["owner", "category"]
    readonly_fields = ["views_count", "slug", "created_at", "updated_at"]
    inlines = [ListingImageInline]
    ordering = ["-created_at"]

    @display(description="Listing", header=True)
    def display_header(self, instance):
        primary_img = instance.images.filter(is_primary=True).first()
        return [
            instance.title,
            f"Owned by: {instance.owner.full_name or instance.owner.email}",
            primary_img.image_url if primary_img else None,
        ]

    @display(description="Category", label=True)
    def display_category(self, instance):
        return instance.category.name if instance.category else "No Category"

    @display(description="Price (Day)", label="success")
    def display_price(self, instance):
        return f"{instance.price_per_day:,.2f} ETB"

    @display(description="Condition", label={
        Listing.Condition.NEW: "success",
        Listing.Condition.LIKE_NEW: "info",
        Listing.Condition.GOOD: "warning",
        Listing.Condition.FAIR: "danger",
    })
    def display_condition(self, instance):
        return instance.condition

    @display(description="Active", boolean=True)
    def display_status(self, instance):
        return instance.is_active

    fieldsets = (
        (None, {"fields": ("title", "slug", "owner", "category")}),
        ("Pricing & Deposit", {
            "classes": ["tab"],
            "fields": ("price_per_day", "price_per_week", "price_per_month", "deposit_amount")
        }),
        ("Details & Location", {
            "classes": ["tab"],
            "fields": ("description", "condition", "city", "address")
        }),
        ("System Metrics", {
            "classes": ["tab"],
            "fields": ("views_count", "is_active", "created_at", "updated_at")
        }),
    )


@admin.register(ListingImage)
class ListingImageAdmin(ModelAdmin):
    list_display = ["listing", "display_preview", "is_primary", "sort_order"]
    list_filter = ["is_primary"]
    search_fields = ["listing__title"]

    @display(description="Preview")
    def display_preview(self, instance):
        return [instance.image_url]
