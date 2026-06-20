from datetime import timedelta
import uuid

from django.utils import timezone

from subscriptions.models import (
    CustomerPremiumSubscription,
    LandlordSubscription,
    PlatformSettings,
    SubscriptionPlan,
)


def ensure_landlord_subscription(user):
    """
    Ensure a landlord has a subscription record for their selected plan.
    Fixes cases where plan was lost from cache after registration.
    """
    if not user.is_landlord or not user.landlord_plan_id:
        return None

    sub = get_active_landlord_subscription(user)
    if sub:
        return sub

    pending = get_pending_landlord_subscription(user)
    if pending:
        return pending

    plan = user.landlord_plan
    if not plan or not plan.is_active:
        return None

    return create_landlord_subscription(user, plan)


def get_active_landlord_subscription(user):
    """Return the landlord's current active subscription, if any."""
    now = timezone.now()
    sub = (
        LandlordSubscription.objects.filter(
            user=user,
            status=LandlordSubscription.Status.ACTIVE,
        )
        .select_related("plan")
        .order_by("-created_at")
        .first()
    )
    if sub and sub.expires_at and sub.expires_at <= now:
        sub.status = LandlordSubscription.Status.EXPIRED
        sub.save(update_fields=["status", "updated_at"])
        return None
    return sub


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


def _count_landlord_listings(user):
    from listings.models import Listing

    return Listing.objects.filter(owner=user, is_active=True).count()


def _count_premium_listings(user):
    from listings.models import Listing

    return Listing.objects.filter(owner=user, is_active=True, is_premium_post=True).count()


def sync_landlord_usage_counters(sub):
    """Sync usage counters from actual database listing counts."""
    sub.posts_used = _count_landlord_listings(sub.user)
    sub.premium_posts_used = _count_premium_listings(sub.user)
    sub.save(update_fields=["posts_used", "premium_posts_used", "updated_at"])
    return sub


def get_landlord_usage(sub):
    """
    Return plan limits and usage from the database.
    Limits come from subscription.plan; usage from active listings count.
    """
    plan = SubscriptionPlan.objects.get(pk=sub.plan_id)
    posts_used = _count_landlord_listings(sub.user)
    premium_used = _count_premium_listings(sub.user)

    if sub.status == LandlordSubscription.Status.ACTIVE:
        sub.posts_used = posts_used
        sub.premium_posts_used = premium_used
        sub.save(update_fields=["posts_used", "premium_posts_used", "updated_at"])
    else:
        sub.posts_used = posts_used
        sub.premium_posts_used = premium_used

    posts_remaining = max(0, plan.max_posts - posts_used)
    premium_remaining = max(0, plan.max_premium_posts - premium_used)
    approvals_remaining = max(0, plan.max_approvals - sub.approvals_used)
    is_active = sub.status == LandlordSubscription.Status.ACTIVE

    return {
        "plan_id": str(plan.id),
        "plan_name": plan.name,
        "plan_type": plan.plan_type,
        "subscription_status": sub.status,
        "payment_status": sub.payment_status,
        "max_posts": plan.max_posts,
        "posts_used": posts_used,
        "posts_remaining": posts_remaining,
        "max_premium_posts": plan.max_premium_posts,
        "premium_posts_used": premium_used,
        "premium_posts_remaining": premium_remaining,
        "max_approvals": plan.max_approvals,
        "approvals_used": sub.approvals_used,
        "approvals_remaining": approvals_remaining,
        "can_post": is_active and posts_remaining > 0,
        "can_create_premium_post": is_active and premium_remaining > 0,
    }


def get_landlord_usage_for_user(user):
    sub = get_active_landlord_subscription(user)
    if not sub:
        return None
    return get_landlord_usage(sub)


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
        ensure_landlord_subscription(user)
        sub = get_active_landlord_subscription(user)
    if not sub:
        pending = get_pending_landlord_subscription(user)
        if pending:
            return False, (
                "Your subscription payment is pending. "
                "Complete payment and verify, or choose a free plan."
            )
        if user.landlord_plan_id:
            return False, (
                "Your subscription plan is not active yet. "
                "Complete payment verification or contact support."
            )
        return False, "No active subscription plan. Please select or renew your plan."

    usage = get_landlord_usage(sub)

    if usage["posts_remaining"] <= 0:
        return False, {
            "detail": (
                f"You have used all {usage['max_posts']} posts on your "
                f"{usage['plan_name']} plan. Upgrade your plan to post more listings."
            ),
            "code": "post_limit_reached",
            **usage,
        }

    if is_premium_post:
        if usage["premium_posts_remaining"] <= 0:
            return False, {
                "detail": (
                    f"You have used all {usage['max_premium_posts']} premium posts on your "
                    f"{usage['plan_name']} plan. Upgrade your plan for more premium listings."
                ),
                "code": "premium_post_limit_reached",
                **usage,
            }

    return True, usage


def increment_landlord_usage(user, is_premium_post=False):
    """Sync usage counters from actual listings after create/update."""
    sub = get_active_landlord_subscription(user)
    if not sub:
        return
    sync_landlord_usage_counters(sub)


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
    usage = get_landlord_usage(sub)
    if usage["approvals_remaining"] <= 0:
        return False, (
            f"Approval limit reached ({usage['approvals_used']} of {usage['max_approvals']} "
            f"on {usage['plan_name']} plan)."
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

    if user.landlord_plan_id != plan.id:
        user.landlord_plan = plan
        user.save(update_fields=["landlord_plan"])

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

    user.landlord_plan = plan
    user.save(update_fields=["landlord_plan"])

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

