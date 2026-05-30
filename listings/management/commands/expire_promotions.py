from django.core.management.base import BaseCommand
from django.utils import timezone
from listings.models import Listing

class Command(BaseCommand):
    help = 'Expires featured listings whose promotion period has passed'

    def handle(self, *args, **kwargs):
        expired_count = Listing.objects.filter(
            is_featured=True,
            featured_until__lt=timezone.now()
        ).update(is_featured=False, featured_until=None)

        if expired_count:
            self.stdout.write(self.style.SUCCESS(f'Successfully expired {expired_count} featured listing(s).'))
        else:
            self.stdout.write(self.style.SUCCESS('No featured listings to expire.'))
