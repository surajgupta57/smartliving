import hashlib
import os
from pathlib import Path
import shutil
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils._os import safe_join
from apps.catalogue.models import ProductDocument


def digest(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


class Command(BaseCommand):
    help = 'Copy old public product documents into private storage, verify hashes, and optionally remove verified public copies. Does not alter database records.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--remove-public-copies', action='store_true')

    def handle(self, *args, **options):
        media = Path(settings.MEDIA_ROOT).resolve()
        private = Path(settings.PRIVATE_DOCUMENT_ROOT).resolve()
        if private == media or media in private.parents or private in media.parents:
            raise CommandError('Private documents and public media roots must be separate and non-overlapping.')
        names = set(ProductDocument.objects.exclude(file='').values_list('file', flat=True))
        plan = []
        for name in sorted(names):
            try:
                source = Path(safe_join(media, name))
                destination = Path(safe_join(private, name))
            except Exception:
                raise CommandError('Unsafe document path in database; no relocation performed.') from None
            if not source.resolve().is_relative_to(media) or not destination.resolve().is_relative_to(private) or source.is_symlink() or destination.is_symlink():
                raise CommandError('Document path crosses a storage boundary; no relocation performed.')
            if not source.is_file() and not destination.is_file():
                raise CommandError('A document is missing from both storage roots; restore it before launch.')
            if source.is_file() and destination.is_file() and digest(source) != digest(destination):
                raise CommandError('Public/private document content differs; resolve the conflict before relocation.')
            plan.append((source, destination))
        if options['dry_run']:
            self.stdout.write(f'{len(plan)} unique document paths checked. Dry run: no files changed.')
            return
        previous_umask = os.umask(0o077)
        try:
            # Complete and verify ALL copies before removing any originals.
            for source, destination in plan:
                if source.is_file() and not destination.is_file():
                    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                    shutil.copyfile(source, destination)
                os.chmod(destination, 0o600)
                if source.is_file() and digest(source) != digest(destination):
                    raise CommandError('Copy verification failed. No public originals have been removed.')
            if options['remove_public_copies']:
                for source, destination in plan:
                    if source.is_file():
                        if digest(source) != digest(destination):
                            raise CommandError('A document changed during relocation; stop uploads and retry.')
                        source.unlink()
        finally:
            os.umask(previous_umask)
        self.stdout.write(self.style.SUCCESS(f'{len(plan)} document paths secured. Public originals {"removed after verification" if options["remove_public_copies"] else "retained: block direct media access until removed"}.'))
