from decimal import Decimal

from django.db import migrations


def seed_defaults(apps, schema_editor):
    PlatformSettings = apps.get_model("subscriptions", "PlatformSettings")
    SubscriptionPlan = apps.get_model("subscriptions", "SubscriptionPlan")
    User = apps.get_model("accounts", "User")

    PlatformSettings.objects.get_or_create(
        pk=1,
        defaults={
            "premium_minimum_price": Decimal("50000.00"),
            "customer_premium_price": Decimal("500.00"),
            "customer_premium_duration_days": 30,
        },
    )

    plans = [
        {
            "name": "Free Plan",
            "slug": "free",
            "plan_type": "free",
            "description": "Get started with 5 listings and 1 approval.",
            "max_posts": 5,
            "max_approvals": 1,
            "max_premium_posts": 0,
            "price": Decimal("0.00"),
            "duration_days": 0,
            "is_active": True,
            "is_default": True,
            "sort_order": 0,
        },
        {
            "name": "Basic Plan",
            "slug": "basic",
            "plan_type": "basic",
            "description": "More listings and approvals for growing landlords.",
            "max_posts": 20,
            "max_approvals": 10,
            "max_premium_posts": 2,
            "price": Decimal("500.00"),
            "duration_days": 30,
            "is_active": True,
            "is_default": False,
            "sort_order": 1,
        },
        {
            "name": "Premium Plan",
            "slug": "premium",
            "plan_type": "premium",
            "description": "Unlimited premium listings for luxury property owners.",
            "max_posts": 50,
            "max_approvals": 50,
            "max_premium_posts": 20,
            "price": Decimal("1500.00"),
            "duration_days": 30,
            "is_active": True,
            "is_default": False,
            "sort_order": 2,
        },
    ]

    for plan_data in plans:
        SubscriptionPlan.objects.get_or_create(slug=plan_data["slug"], defaults=plan_data)

    # Existing users before this feature should remain usable
    User.objects.filter(email_verified=False).update(
        email_verified=True,
        account_status="active",
    )


def reverse_seed(apps, schema_editor):
    SubscriptionPlan = apps.get_model("subscriptions", "SubscriptionPlan")
    PlatformSettings = apps.get_model("subscriptions", "PlatformSettings")
    SubscriptionPlan.objects.filter(slug__in=["free", "basic", "premium"]).delete()
    PlatformSettings.objects.filter(pk=1).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("subscriptions", "0001_initial"),
        ("accounts", "0002_user_account_status_user_email_verified_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_defaults, reverse_seed),
    ]
