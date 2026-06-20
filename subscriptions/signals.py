from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import PlatformSettings, SubscriptionPlan


@receiver(post_save, sender=SubscriptionPlan)
def ensure_single_default_plan(sender, instance, **kwargs):
    """Only one plan can be marked as default at a time."""
    if instance.is_default:
        SubscriptionPlan.objects.filter(is_default=True).exclude(pk=instance.pk).update(
            is_default=False
        )


def ensure_platform_settings():
    PlatformSettings.get_settings()
