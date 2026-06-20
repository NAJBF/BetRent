import uuid

from django.conf import settings
from django.db import models

from core.models import BaseModel


class PlatformSettings(models.Model):
    """
    Singleton platform configuration editable from Django admin.
    Controls premium listing minimum price and other global settings.
    """

    premium_minimum_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=50000,
        help_text="Minimum monthly price (ETB) required for a listing to be marked as premium.",
    )
    customer_premium_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=500,
        help_text="Price (ETB) for customer premium subscription.",
    )
    customer_premium_duration_days = models.PositiveIntegerField(
        default=30,
        help_text="Duration in days for customer premium subscription.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Platform Settings"
        verbose_name_plural = "Platform Settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def get_settings(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return "Platform Settings"


class SubscriptionPlan(BaseModel):
    """
    Configurable landlord subscription plan (Free, Basic, Premium).
    Default plans are seeded via data migration.
    """

    class PlanType(models.TextChoices):
        FREE = "free", "Free"
        BASIC = "basic", "Basic"
        PREMIUM = "premium", "Premium"

    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True)
    plan_type = models.CharField(max_length=20, choices=PlanType.choices)
    description = models.TextField(blank=True, default="")

    max_posts = models.PositiveIntegerField(
        help_text="Maximum active listings allowed.",
    )
    max_approvals = models.PositiveIntegerField(
        help_text="Maximum booking approvals per billing period.",
    )
    max_premium_posts = models.PositiveIntegerField(
        help_text="Maximum premium listings allowed.",
    )

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Plan price in ETB (0 for free plan).",
    )
    duration_days = models.PositiveIntegerField(
        default=30,
        help_text="Billing period in days (0 = unlimited for free plan).",
    )

    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(
        default=False,
        help_text="Default plan shown during landlord registration.",
    )
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "price"]

    def __str__(self):
        return f"{self.name} ({self.plan_type})"


class LandlordSubscription(BaseModel):
    """Tracks a landlord's active or pending subscription."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACTIVE = "active", "Active"
        EXPIRED = "expired", "Expired"
        CANCELLED = "cancelled", "Cancelled"

    class PaymentStatus(models.TextChoices):
        NOT_REQUIRED = "not_required", "Not Required"
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="landlord_subscriptions",
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name="subscriptions",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    payment_status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    transaction_ref = models.CharField(max_length=100, unique=True, blank=True)
    checkout_url = models.URLField(blank=True, default="")
    starts_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    # Usage counters for current billing period
    posts_used = models.PositiveIntegerField(default=0)
    approvals_used = models.PositiveIntegerField(default=0)
    premium_posts_used = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} — {self.plan.name} ({self.status})"

    def save(self, *args, **kwargs):
        if not self.transaction_ref:
            self.transaction_ref = f"LSUB-{uuid.uuid4().hex[:12].upper()}"
        super().save(*args, **kwargs)

    @property
    def can_post(self):
        return (
            self.status == self.Status.ACTIVE
            and self.posts_used < self.plan.max_posts
        )

    @property
    def can_create_premium_post(self):
        return (
            self.can_post
            and self.premium_posts_used < self.plan.max_premium_posts
        )

    @property
    def can_approve(self):
        return (
            self.status == self.Status.ACTIVE
            and self.approvals_used < self.plan.max_approvals
        )


class CustomerPremiumSubscription(BaseModel):
    """Premium customer subscription for viewing luxury/premium listings."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACTIVE = "active", "Active"
        EXPIRED = "expired", "Expired"
        CANCELLED = "cancelled", "Cancelled"

    class PaymentStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="premium_subscription",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    payment_status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    transaction_ref = models.CharField(max_length=100, unique=True, blank=True)
    checkout_url = models.URLField(blank=True, default="")
    starts_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Premium Customer: {self.user.email} ({self.status})"

    def save(self, *args, **kwargs):
        if not self.transaction_ref:
            self.transaction_ref = f"CPREM-{uuid.uuid4().hex[:12].upper()}"
        super().save(*args, **kwargs)
