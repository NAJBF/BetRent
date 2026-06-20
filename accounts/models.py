from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", "admin")
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """
    BetRent custom user model with email-based authentication.
    Roles: customer, landlord, admin.
    """

    class Role(models.TextChoices):
        CUSTOMER = "customer", "Customer"
        LANDLORD = "landlord", "Landlord"
        ADMIN = "admin", "Admin"

    username = models.CharField(max_length=150, unique=True, blank=True, null=True)
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=255, blank=True, default="")
    phone = models.CharField(max_length=20, blank=True, default="")
    city = models.CharField(max_length=100, blank=True, default="")
    bio = models.TextField(blank=True, default="")
    avatar_url = models.URLField(blank=True, default="")
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CUSTOMER,
    )

    class AccountStatus(models.TextChoices):
        PENDING_EMAIL = "pending_email", "Pending Email Verification"
        PENDING_PAYMENT = "pending_payment", "Pending Payment Verification"
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"

    email_verified = models.BooleanField(default=False)
    account_status = models.CharField(
        max_length=30,
        choices=AccountStatus.choices,
        default=AccountStatus.PENDING_EMAIL,
    )
    is_premium_customer = models.BooleanField(default=False)
    premium_until = models.DateTimeField(null=True, blank=True)
    landlord_plan = models.ForeignKey(
        "subscriptions.SubscriptionPlan",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="landlord_users",
        help_text="Selected subscription plan for landlord accounts.",
    )

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = "user"
        verbose_name_plural = "users"

    def __str__(self):
        return self.email

    @property
    def is_admin(self):
        return self.role == self.Role.ADMIN or self.is_superuser

    @property
    def is_landlord(self):
        return self.role in (self.Role.LANDLORD, self.Role.ADMIN)

    @property
    def can_post_listings(self):
        """Landlords can post only when email verified and account is active."""
        if not self.is_landlord:
            return False
        if not self.email_verified:
            return False
        return self.account_status == self.AccountStatus.ACTIVE

    @property
    def can_view_premium_listings(self):
        """Premium customers (or admins) can view premium listings."""
        if self.role == self.Role.ADMIN:
            return True
        if not self.is_premium_customer:
            return False
        if self.premium_until:
            from django.utils import timezone
            return self.premium_until > timezone.now()
        return True
