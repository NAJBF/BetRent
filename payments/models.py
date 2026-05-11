import uuid
from django.db import models
from core.models import BaseModel


class Payment(BaseModel):
    """
    Payment record linked to a booking.
    Supports Chapa, bank transfer, and cash methods.
    """

    class Method(models.TextChoices):
        CHAPA = "chapa", "Chapa"
        BANK_TRANSFER = "bank_transfer", "Bank Transfer"
        CASH = "cash", "Cash"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    booking = models.OneToOneField(
        "bookings.Booking",
        on_delete=models.CASCADE,
        related_name="payment",
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    method = models.CharField(
        max_length=20, choices=Method.choices, default=Method.CHAPA
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    transaction_ref = models.CharField(max_length=100, unique=True, blank=True)
    checkout_url = models.URLField(blank=True, default="")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Payment {self.transaction_ref} — {self.status}"

    def save(self, *args, **kwargs):
        if not self.transaction_ref:
            self.transaction_ref = f"BETRENT-{uuid.uuid4().hex[:12].upper()}"
        super().save(*args, **kwargs)
