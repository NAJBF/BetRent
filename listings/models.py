from django.db import models
from django.conf import settings
from core.models import BaseModel
from core.mixins import generate_unique_slug


class Listing(BaseModel):
    """
    Core rental listing — houses, vehicles, electronics, furniture, etc.
    Supports multi-tier pricing (daily/weekly/monthly) and soft delete.
    """

    class Condition(models.TextChoices):
        NEW = "new", "New"
        LIKE_NEW = "like_new", "Like New"
        GOOD = "good", "Good"
        FAIR = "fair", "Fair"

    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, unique=True, blank=True)
    description = models.TextField()

    # Multi-tier pricing (ETB)
    price_per_day = models.DecimalField(max_digits=12, decimal_places=2)
    price_per_week = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    price_per_month = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    deposit_amount = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, default=0
    )

    condition = models.CharField(
        max_length=20, choices=Condition.choices, default=Condition.GOOD
    )
    city = models.CharField(max_length=100)
    address = models.CharField(max_length=255, blank=True, default="")

    views_count = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    # Relationships
    category = models.ForeignKey(
        "categories.Category",
        on_delete=models.SET_NULL,
        null=True,
        related_name="listings",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="listings",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["city"]),
            models.Index(fields=["price_per_day"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = generate_unique_slug(Listing, self.title)
        super().save(*args, **kwargs)

    def increment_views(self):
        """Atomically increment the view counter."""
        Listing.objects.filter(pk=self.pk).update(
            views_count=models.F("views_count") + 1
        )
        self.refresh_from_db(fields=["views_count"])


class ListingImage(BaseModel):
    """Image URL attached to a listing, with primary flag and sort order."""

    listing = models.ForeignKey(
        Listing, on_delete=models.CASCADE, related_name="images"
    )
    image_url = models.URLField(max_length=500)
    is_primary = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "-is_primary"]

    def __str__(self):
        return f"Image for {self.listing.title} ({'primary' if self.is_primary else 'secondary'})"

    def save(self, *args, **kwargs):
        # If this image is marked primary, unset other primaries for the listing
        if self.is_primary:
            ListingImage.objects.filter(
                listing=self.listing, is_primary=True
            ).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)
