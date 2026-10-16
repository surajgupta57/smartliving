"""Read-only application checks before opening production traffic."""
import os
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from urllib.parse import urlsplit
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.storage import staticfiles_storage
from django.core.checks import WARNING, run_checks
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


class Command(BaseCommand):
    help = 'Check production settings, database, migrations, assets and operator setup without modifying data.'
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument('--configuration-only', action='store_true', help='Skip database, assets and business-data checks.')

    def handle(self, *args, **options):
        if getattr(settings, 'ENVIRONMENT', '') != 'production':
            raise CommandError('Select config.production or DJANGO_ENV=production first.')
        lock = Path(settings.BASE_DIR) / 'requirements-production.txt'
        if not lock.is_file():
            raise CommandError('The tested production dependency file is missing.')
        mismatched = []
        for line in lock.read_text(encoding='utf-8').splitlines():
            if '==' not in line or line.lstrip().startswith('#'):
                continue
            package, expected = line.strip().split('==', 1)
            try:
                if version(package) != expected:
                    mismatched.append(package)
            except PackageNotFoundError:
                mismatched.append(package)
        if mismatched:
            raise CommandError('Install the tested requirements-production.txt package set before launch. Mismatched packages: ' + ', '.join(mismatched))
        # Deliberately do not preload HSTS or extend it to unreviewed child hosts.
        acknowledged = {'security.W005', 'security.W021'}
        problems = [item for item in run_checks(include_deployment_checks=True) if item.level >= WARNING and item.id not in acknowledged]
        if problems:
            raise CommandError('\n'.join(str(item) for item in problems))
        self.stdout.write('Production configuration and Django deployment checks passed.')
        self.stdout.write('Intentional HSTS scope: child subdomains and browser preload remain disabled (W005/W021).')
        if options['configuration_only']:
            self.stdout.write('Configuration-only: database, migrations, assets, business identity and staff access were NOT checked.')
            return
        failures = []
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
                cursor.fetchone()
            executor = MigrationExecutor(connection)
            if executor.migration_plan(executor.loader.graph.leaf_nodes()):
                failures.append('Unapplied migrations: run migrate after a verified backup.')
        except Exception:
            raise CommandError('Database or migration check failed. Verify database settings privately; no credentials were printed.') from None
        for name in ['css/site.css', 'css/workspace.css', 'js/site.js', 'js/workspace-layout.js', 'js/workspace-reminders.js', 'admin/css/base.css']:
            try:
                staticfiles_storage.url(name)
                if not staticfiles_storage.exists(staticfiles_storage.stored_name(name)):
                    failures.append(f'Missing collected static asset: {name}')
            except (ValueError, OSError):
                failures.append(f'Missing static manifest entry: {name}. Run collectstatic.')
        for label, path in [('media', settings.MEDIA_ROOT), ('private imports', settings.STORAGES['import_export']['OPTIONS']['location']), ('private documents', settings.PRIVATE_DOCUMENT_ROOT)]:
            if not os.path.isdir(path) or not os.access(path, os.W_OK):
                failures.append(f'The {label} directory must exist and be writable by the application user.')
        from apps.core.models import SiteSettings
        from apps.catalogue.models import Product
        from apps.catalogue.models import ProductDocument
        from django.utils._os import safe_join
        for document in ProductDocument.objects.exclude(file='').iterator():
            try:
                if not document.file.storage.exists(document.file.name):
                    failures.append('A product document is missing from private storage. Run secure_product_documents after transferring the files.')
                    break
                if os.path.isfile(safe_join(settings.MEDIA_ROOT, document.file.name)):
                    failures.append('Public copies of product documents remain. Back up, then run secure_product_documents --remove-public-copies.')
                    break
            except Exception:
                failures.append('An unsafe product-document path needs administrator review.')
                break
        site = SiteSettings.objects.first()
        if not site or not all([site.company_name.strip(), site.phone.strip(), site.email.strip(), site.address.strip()]):
            failures.append('Complete the real business name, phone, email and address in Site settings.')
        if site:
            public = urlsplit(site.public_url)
            if public.scheme != 'https' or public.netloc not in settings.ALLOWED_HOSTS or public.query or public.fragment or public.path not in ('', '/'):
                failures.append('Site settings public URL must match the production HTTPS hostname.')
        if not Product.objects.filter(is_active=True, is_published=True).exists():
            failures.append('No active published products are available.')
        has_operator = any(user.has_perm('leads.view_enquiry') and user.has_perm('leads.change_enquiry') for user in get_user_model().objects.filter(is_active=True, is_staff=True).iterator())
        if not has_operator:
            failures.append('Approve an active staff operator with view/change enquiry permissions.')
        if failures:
            raise CommandError('\n'.join(failures))
        self.stdout.write(self.style.SUCCESS('Application preflight passed. Still verify host HTTPS/proxy behavior, public assets, private-path protection, backups/restore and a real browser workflow.'))
