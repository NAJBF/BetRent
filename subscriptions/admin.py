from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin
from unfold.decorators import display

from .models import (
    CustomerPremiumSubscription,
    LandlordSubscription,
    PlatformSettings,
    SubscriptionPlan,
)
from .services import activate_customer_premium, activate_landlord_subscription


@admin.register(PlatformSettings)
class PlatformSettingsAdmin(ModelAdmin):
    list_display = ["premium_minimum_price", "customer_premium_price", "customer_premium_duration_days", "updated_at"]

    def has_add_permission(self, request):
        return not PlatformSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(ModelAdmin):
    list_display = [
        "name",
        "plan_type",
        "max_posts",
        "max_approvals",
        "max_premium_posts",
        "price",
        "duration_days",
        "is_active",
        "is_default",
        "sort_order",
    ]
    list_filter = ["plan_type", "is_active"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    ordering = ["sort_order", "price"]


@admin.register(LandlordSubscription)
class LandlordSubscriptionAdmin(ModelAdmin):
    list_display = [
        "transaction_ref",
        "user",
        "plan",
        "status",
        "payment_status",
        "amount",
        "posts_used",
        "approvals_used",
        "premium_posts_used",
        "created_at",
    ]
    list_editable = ["status", "payment_status"]
    list_filter = ["status", "payment_status", "plan"]
    search_fields = ["transaction_ref", "user__email"]
    readonly_fields = ["transaction_ref", "created_at", "updated_at"]
    autocomplete_fields = ["user", "plan"]
    ordering = ["-created_at"]

    def save_model(self, request, obj, form, change):
        if change and "payment_status" in form.changed_data:
            if obj.payment_status == LandlordSubscription.PaymentStatus.COMPLETED:
                if obj.status != LandlordSubscription.Status.ACTIVE:
                    activate_landlord_subscription(obj)
                    return
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for instance in instances:
            if instance.pk:
                orig = LandlordSubscription.objects.get(pk=instance.pk)
                if (
                    orig.payment_status != LandlordSubscription.PaymentStatus.COMPLETED
                    and instance.payment_status == LandlordSubscription.PaymentStatus.COMPLETED
                    and instance.status != LandlordSubscription.Status.ACTIVE
                ):
                    activate_landlord_subscription(instance)
                    continue
            instance.save()
        formset.save_m2m()


@admin.register(CustomerPremiumSubscription)
class CustomerPremiumSubscriptionAdmin(ModelAdmin):
    list_display = [
        "transaction_ref",
        "user",
        "status",
        "payment_status",
        "amount",
        "starts_at",
        "expires_at",
        "created_at",
    ]
    list_editable = ["status", "payment_status"]
    list_filter = ["status", "payment_status"]
    search_fields = ["transaction_ref", "user__email"]
    readonly_fields = ["transaction_ref", "created_at", "updated_at"]
    autocomplete_fields = ["user"]
    ordering = ["-created_at"]

    def save_model(self, request, obj, form, change):
        if change and "payment_status" in form.changed_data:
            if obj.payment_status == CustomerPremiumSubscription.PaymentStatus.COMPLETED:
                if obj.status != CustomerPremiumSubscription.Status.ACTIVE:
                    activate_customer_premium(obj)
                    return
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for instance in instances:
            if instance.pk:
                orig = CustomerPremiumSubscription.objects.get(pk=instance.pk)
                if (
                    orig.payment_status != CustomerPremiumSubscription.PaymentStatus.COMPLETED
                    and instance.payment_status == CustomerPremiumSubscription.PaymentStatus.COMPLETED
                    and instance.status != CustomerPremiumSubscription.Status.ACTIVE
                ):
                    activate_customer_premium(instance)
                    continue
            instance.save()
        formset.save_m2m()
