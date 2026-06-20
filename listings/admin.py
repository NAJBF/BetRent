from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import display
from .models import Listing, ListingImage, PromotionPayment


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
        "display_featured",
        "display_premium",
        "views_count",
    ]
    list_filter = ["is_active", "is_featured", "is_premium_post", "condition", "city", "category"]
    search_fields = ["title", "description", "city", "owner__email"]
    autocomplete_fields = ["owner", "category"]
    readonly_fields = ["views_count", "slug", "created_at", "updated_at"]
    inlines = [ListingImageInline]
    ordering = ["-is_featured", "-created_at"]

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

    @display(description="Featured", boolean=True)
    def display_featured(self, instance):
        return instance.is_featured

    @display(description="Premium Post", boolean=True)
    def display_premium(self, instance):
        return instance.is_premium_post

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
        ("Premium & Featured", {
            "classes": ["tab"],
            "fields": ("is_premium_post", "is_featured", "featured_until")
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


@admin.register(PromotionPayment)
class PromotionPaymentAdmin(ModelAdmin):
    list_display = [
        "transaction_ref",
        "listing",
        "payer",
        "duration_days",
        "amount",
        "status",
        "created_at",
    ]
    list_editable = ["status"]
    list_filter = ["status", "duration_days"]
    search_fields = ["transaction_ref", "listing__title", "payer__email"]
    readonly_fields = ["transaction_ref", "created_at", "updated_at"]
    ordering = ["-created_at"]

    def save_model(self, request, obj, form, change):
        # If the status is manually changed to COMPLETED in the admin detail view
        if change and "status" in form.changed_data:
            if obj.status == PromotionPayment.Status.COMPLETED:
                from django.utils import timezone
                from datetime import timedelta
                
                # Activate featured listing
                obj.listing.is_featured = True
                obj.listing.featured_until = timezone.now() + timedelta(days=obj.duration_days)
                obj.listing.save(update_fields=["is_featured", "featured_until"])
                
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        # Handle list_editable saves
        instances = formset.save(commit=False)
        for instance in instances:
            # Check if status was changed in the list view
            if instance.pk:
                orig = PromotionPayment.objects.get(pk=instance.pk)
                if orig.status != PromotionPayment.Status.COMPLETED and instance.status == PromotionPayment.Status.COMPLETED:
                    from django.utils import timezone
                    from datetime import timedelta
                    instance.listing.is_featured = True
                    instance.listing.featured_until = timezone.now() + timedelta(days=instance.duration_days)
                    instance.listing.save(update_fields=["is_featured", "featured_until"])
            instance.save()
        formset.save_m2m()

