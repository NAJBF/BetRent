from decimal import Decimal
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from core.models import BaseModel


class Booking(BaseModel):
    """
    Rental booking with auto-price calculation based on duration tier.
    Includes date conflict detection and status workflow.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        PAID = "paid", "Paid"
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    listing = models.ForeignKey(
        "listings.Listing",
        on_delete=models.CASCADE,
        related_name="bookings",
    )
    renter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bookings",
    )
    start_date = models.DateField()
    end_date = models.DateField()
    total_price = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    deposit_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    note = models.TextField(blank=True, default="")
    cancellation_reason = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["start_date", "end_date"]),
        ]

    def __str__(self):
        return f"Booking {self.id} — {self.listing.title} ({self.status})"

    def clean(self):
        """Validate booking constraints."""
        if self.start_date and self.end_date:
            if self.start_date >= self.end_date:
                raise ValidationError("End date must be after start date.")

        # Self-booking prevention
        if self.listing_id and self.renter_id:
            if self.listing.owner_id == self.renter_id:
                raise ValidationError("You cannot book your own listing.")

    def calculate_total_price(self):
        """
        Auto-calculate price based on rental duration tier:
        - 30+ days → monthly rate
        - 7–29 days → weekly rate
        - < 7 days → daily rate
        """
        days = (self.end_date - self.start_date).days
        listing = self.listing

        if days >= 30 and listing.price_per_month:
            months = Decimal(days) / Decimal(30)
            self.total_price = (listing.price_per_month * months).quantize(Decimal("0.01"))
        elif days >= 7 and listing.price_per_week:
            weeks = Decimal(days) / Decimal(7)
            self.total_price = (listing.price_per_week * weeks).quantize(Decimal("0.01"))
        else:
            self.total_price = listing.price_per_day * days

        # Copy deposit from listing
        self.deposit_amount = listing.deposit_amount or Decimal("0")

    @staticmethod
    def check_date_conflict(listing_id, start_date, end_date, exclude_id=None):
        """
        Check for overlapping approved/active/paid bookings.
        Returns True if there is a conflict.
        """
        conflicting = Booking.objects.filter(
            listing_id=listing_id,
            status__in=["approved", "paid", "active"],
            start_date__lt=end_date,
            end_date__gt=start_date,
        )
        if exclude_id:
            conflicting = conflicting.exclude(pk=exclude_id)
        return conflicting.exists()

    # Valid status transitions — bookings are free; no payment step required
    VALID_TRANSITIONS = {
        "pending": ["approved", "rejected", "cancelled"],
        "approved": ["active", "cancelled"],
        "paid": ["active", "cancelled"],
        "active": ["completed"],
    }

    def can_transition_to(self, new_status):
        """Check if the status transition is allowed."""
        allowed = self.VALID_TRANSITIONS.get(self.status, [])
        return new_status in allowed

    def save(self, *args, **kwargs):
        if not self.total_price and self.start_date and self.end_date:
            self.calculate_total_price()
        super().save(*args, **kwargs)
