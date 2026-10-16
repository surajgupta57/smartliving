from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db.models import ImageField

from apps.core.image_variants import generate


class Command(BaseCommand):
    help = 'Generate lossless WebP display copies of public images; never replace originals or database paths.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Calculate potential image sizes without writing files.')
        parser.add_argument('--limit', type=int, default=0, help='Maximum unique images; 0 processes all.')

    def handle(self, *args, **options):
        if options['limit'] < 0:
            raise CommandError('--limit must be zero or positive.')
        seen = set()
        processed = cached = failed = source_bytes = smallest_bytes = 0
        for label in ('catalogue', 'cms', 'core'):
            for model in apps.get_app_config(label).get_models():
                fields = [field for field in model._meta.fields if isinstance(field, ImageField)]
                if not fields:
                    continue
                for record in model.objects.only('pk', *(field.name for field in fields)).iterator(chunk_size=200):
                    for field in fields:
                        image = getattr(record, field.name)
                        if not image or image.name in seen or (options['limit'] and len(seen) >= options['limit']):
                            continue
                        seen.add(image.name)
                        try:
                            result = generate(image, dry_run=options['dry_run'])
                            cached += result['status'] == 'cached'
                            processed += result['status'] == 'generated'
                            source_bytes += result['original']
                            smallest_bytes += min([item['bytes'] for item in result['variants']] or [result['original']])
                        except (OSError, ValueError, TypeError, KeyError, NotImplementedError) as exc:
                            failed += 1
                            self.stderr.write(f'Skipped {model._meta.label} #{record.pk} {field.name}: {type(exc).__name__}')
        self.stdout.write(f'Unique images: {len(seen)}; generated: {processed}; already prepared: {cached}; errors: {failed}.')
        self.stdout.write(f'Original total: {source_bytes / 1048576:.2f} MiB; smallest display copies: {smallest_bytes / 1048576:.2f} MiB. This is not a page-speed benchmark.')
        self.stdout.write('Dry run: no files changed.' if options['dry_run'] else 'Originals and database paths preserved. Repeat after new uploads; unchanged images are skipped.')
        if failed:
            raise CommandError('Some images could not be processed; inspect the summary. Existing images still use their originals.')
