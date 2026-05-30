import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task
def expire_featured_listings():
    """
    Periodic task: disable featured status on listings whose
    promotion period has expired. Scheduled via CELERY_BEAT_SCHEDULE.
    """
    from .models import Listing

    expired_count = Listing.objects.filter(
        is_featured=True,
        featured_until__lt=timezone.now(),
    ).update(is_featured=False, featured_until=None)

    if expired_count:
        logger.info(f"Expired {expired_count} featured listing(s).")

    return f"Expired {expired_count} featured listing(s)."
