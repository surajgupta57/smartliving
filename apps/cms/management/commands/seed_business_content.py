from django.core.management.base import BaseCommand
from django.db import transaction
from apps.cms.business_content import PAGES
from apps.cms.models import ContentPage


class Command(BaseCommand):
    help = 'Add catalogue-based solutions, services and project guides without overwriting existing pages.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Validate and report without saving.')

    @transaction.atomic
    def handle(self, *args, **options):
        created = skipped = 0
        for index, content in enumerate(PAGES):
            if ContentPage.objects.filter(kind=content['kind'], slug=content['slug']).exists():
                skipped += 1
                continue
            record = ContentPage(**content, display_order=(index + 1) * 10)
            record.full_clean()
            if not options['dry_run']:
                record.save()
            created += 1
        action = 'Would create' if options['dry_run'] else 'Created'
        self.stdout.write(self.style.SUCCESS(f'{action} {created} pages; preserved {skipped} existing pages.'))
