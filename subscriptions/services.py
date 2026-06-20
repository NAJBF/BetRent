from datetime import timedelta
import uuid

from django.utils import timezone

from subscriptions.models import (
    CustomerPremiumSubscription,
    LandlordSubscription,
    PlatformSettings,
    SubscriptionPlan,
)


def get_active_landlord_subscription(user):
    """Return the landlord's current active subscription, if any."""
    return (
        LandlordSubscription.objects.filter(
            user=user,
            status=LandlordSubscription.Status.ACTIVE,
        )
        .select_related("plan")
        .order_by("-created_at")
        .first()
    )


def get_pending_landlord_subscription(user):
    return (
        LandlordSubscription.objects.filter(
            user=user,
            status=LandlordSubscription.Status.PENDING,
        )
        .select_related("plan")
        .order_by("-created_at")
        .first()
    )


def activate_landlord_subscription(subscription):
    """Activate a landlord subscription after payment verification."""
    now = timezone.now()
    duration = subscription.plan.duration_days
    subscription.status = LandlordSubscription.Status.ACTIVE
    subscription.payment_status = LandlordSubscription.PaymentStatus.COMPLETED
    subscription.starts_at = now
    subscription.expires_at = (
        now + timedelta(days=duration) if duration > 0 else None
    )
    subscription.posts_used = 0
    subscription.approvals_used = 0
    subscription.premium_posts_used = 0
    subscription.save()

    user = subscription.user
    user.account_status = user.AccountStatus.ACTIVE
    user.is_active = True
    user.save(update_fields=["account_status", "is_active"])


def activate_customer_premium(subscription):
    """Activate customer premium subscription after payment verification."""
    settings = PlatformSettings.get_settings()
    now = timezone.now()
    duration = settings.customer_premium_duration_days

    subscription.status = CustomerPremiumSubscription.Status.ACTIVE
    subscription.payment_status = CustomerPremiumSubscription.PaymentStatus.COMPLETED
    subscription.starts_at = now
    subscription.expires_at = now + timedelta(days=duration)
    subscription.save()

    user = subscription.user
    user.is_premium_customer = True
    user.premium_until = subscription.expires_at
    user.save(update_fields=["is_premium_customer", "premium_until"])


def check_landlord_can_post(user, is_premium_post=False):
    """
    Validate landlord posting limits.
    Returns (allowed: bool, error_message: str | None).
    """
    if not user.can_post_listings:
        if user.account_status == user.AccountStatus.PENDING_EMAIL:
            return False, "Please verify your email before posting."
        if user.account_status == user.AccountStatus.PENDING_PAYMENT:
            return False, "Your account is pending payment verification. Posting is not allowed yet."
        return False, "You are not allowed to post listings at this time."

    sub = get_active_landlord_subscription(user)
    if not sub:
        return False, "No active subscription plan. Please select or renew your plan."

    if sub.posts_used >= sub.plan.max_posts:
        return False, f"Post limit reached ({sub.plan.max_posts} posts on {sub.plan.name} plan)."

    if is_premium_post:
        if sub.premium_posts_used >= sub.plan.max_premium_posts:
            return False, (
                f"Premium post limit reached ({sub.plan.max_premium_posts} "
                f"on {sub.plan.name} plan)."
            )

    return True, None


def increment_landlord_usage(user, is_premium_post=False):
    """Increment usage counters after successful listing creation."""
    sub = get_active_landlord_subscription(user)
    if not sub:
        return
    sub.posts_used += 1
    if is_premium_post:
        sub.premium_posts_used += 1
    sub.save(update_fields=["posts_used", "premium_posts_used", "updated_at"])


def increment_approval_usage(landlord):
    """Increment approval counter when landlord approves a booking."""
    sub = get_active_landlord_subscription(landlord)
    if not sub:
        return
    sub.approvals_used += 1
    sub.save(update_fields=["approvals_used", "updated_at"])


def check_landlord_can_approve(landlord):
    """Validate landlord approval limits."""
    sub = get_active_landlord_subscription(landlord)
    if not sub:
        return False, "No active subscription plan."
    if sub.approvals_used >= sub.plan.max_approvals:
        return False, (
            f"Approval limit reached ({sub.plan.max_approvals} "
            f"on {sub.plan.name} plan)."
        )
    return True, None


def validate_premium_post_price(listing):
    """
    Validate that a premium post meets the minimum price threshold.
    Uses monthly price if set, otherwise daily price * 30.
    """
    settings = PlatformSettings.get_settings()
    min_price = settings.premium_minimum_price

    if listing.price_per_month:
        effective_price = listing.price_per_month
    else:
        effective_price = listing.price_per_day * 30

    if effective_price < min_price:
        return False, (
            f"Premium listings require a minimum price of {min_price} ETB/month. "
            f"Your listing price is {effective_price} ETB/month equivalent."
        )
    return True, None


def create_landlord_subscription(user, plan):
    """
    Create a landlord subscription for the given plan.
    Free plans activate immediately; paid plans stay pending until payment.
    """
    is_free = plan.price <= 0 or plan.plan_type == SubscriptionPlan.PlanType.FREE

    subscription = LandlordSubscription.objects.create(
        user=user,
        plan=plan,
        amount=plan.price,
        status=LandlordSubscription.Status.PENDING,
        payment_status=(
            LandlordSubscription.PaymentStatus.NOT_REQUIRED
            if is_free
            else LandlordSubscription.PaymentStatus.PENDING
        ),
    )

    if is_free:
        activate_landlord_subscription(subscription)
    else:
        user.account_status = user.AccountStatus.PENDING_PAYMENT
        user.save(update_fields=["account_status"])

    return subscription


def upgrade_landlord_plan(user, plan):
    """Upgrade or change landlord plan — cancels current active/pending and creates new."""
    LandlordSubscription.objects.filter(
        user=user,
        status__in=[
            LandlordSubscription.Status.ACTIVE,
            LandlordSubscription.Status.PENDING,
        ],
    ).update(status=LandlordSubscription.Status.CANCELLED)

    return create_landlord_subscription(user, plan)


def initiate_customer_premium_upgrade(user):
    """Create or reset a pending customer premium subscription with checkout ref."""
    settings = PlatformSettings.get_settings()
    subscription, created = CustomerPremiumSubscription.objects.get_or_create(
        user=user,
        defaults={
            "amount": settings.customer_premium_price,
            "status": CustomerPremiumSubscription.Status.PENDING,
            "payment_status": CustomerPremiumSubscription.PaymentStatus.PENDING,
        },
    )

    if not created and subscription.payment_status != CustomerPremiumSubscription.PaymentStatus.COMPLETED:
        subscription.amount = settings.customer_premium_price
        subscription.status = CustomerPremiumSubscription.Status.PENDING
        subscription.payment_status = CustomerPremiumSubscription.PaymentStatus.PENDING
        subscription.transaction_ref = f"CPREM-{uuid.uuid4().hex[:12].upper()}"
        subscription.checkout_url = ""
        subscription.save()

    return subscription, settings.customer_premium_price

