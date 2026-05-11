from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from core.models import BaseModel


class Review(BaseModel):
    """
    Verified review — only renters with completed bookings can review.
    One review per listing per user (enforced by unique constraint).
    """

    listing = models.ForeignKey(
        "listings.Listing",
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    comment = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["listing", "reviewer"],
                name="unique_review_per_listing_per_user",
            )
        ]

    def __str__(self):
        return f"Review by {self.reviewer.email} — {self.listing.title} ({self.rating}⭐)"
