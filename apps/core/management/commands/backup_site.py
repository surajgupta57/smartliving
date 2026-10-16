"""Create private database and media backups without exposing database credentials."""
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


def private_backup_root(value):
    root = Path(value).expanduser().resolve()
    public = [Path(settings.MEDIA_ROOT).resolve(), Path(settings.STATIC_ROOT).resolve(), Path(settings.PRIVATE_DOCUMENT_ROOT).resolve()]
    if any(part.lower() in {'public_html', 'htdocs', 'httpdocs', 'www'} for part in root.parts) or any(root == path or path in root.parents for path in public):
        raise CommandError('Backups must be outside public roots, media and static directories.')
    return root


def mysql_option(value):
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r') + '"'


class Command(BaseCommand):
    help = 'Back up production MySQL and media to an explicit private directory. Does not modify application records.'
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument('--output-dir', required=True)
        parser.add_argument('--mysqldump', default='mysqldump', help='Host path to the MySQL dump binary.')

    def handle(self, *args, **options):
        database = settings.DATABASES['default']
        if getattr(settings, 'ENVIRONMENT', '') != 'production' or database['ENGINE'] != 'django.db.backends.mysql':
            raise CommandError('Select the production MySQL configuration before backing up.')
        root = private_backup_root(options['output_dir'])
        stores = {'media': Path(settings.MEDIA_ROOT).resolve(), 'private_documents': Path(settings.PRIVATE_DOCUMENT_ROOT).resolve()}
        if any(not path.is_dir() for path in stores.values()):
            raise CommandError('Media/private documents directory is missing; refusing an incomplete backup.')
        binary = shutil.which(options['mysqldump'])
        if not binary:
            raise CommandError('mysqldump is unavailable. Ask the host for its path.')
        previous_umask = os.umask(0o077)
        process = None
        try:
            root.mkdir(parents=True, exist_ok=True)
            destination = root / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
            destination.mkdir(mode=0o700)
            (destination / 'INCOMPLETE').touch(mode=0o600)
            # The password is passed only in a private temporary MySQL option file,
            # never through argv, logs or an exported environment variable.
            with tempfile.TemporaryDirectory(prefix='smartliving-backup-', dir=destination) as temp:
                config = Path(temp) / 'mysql.cnf'
                values = {'user': database['USER'], 'password': database['PASSWORD'], 'host': database.get('HOST') or 'localhost', 'port': database.get('PORT') or 3306}
                config.write_text('[client]\n' + ''.join(f'{key}={mysql_option(value)}\n' for key, value in values.items()), encoding='utf-8')
                os.chmod(config, 0o600)
                with tempfile.TemporaryFile() as errors:
                    process = subprocess.Popen([binary, f'--defaults-extra-file={config}', '--single-transaction', '--quick', '--no-tablespaces', '--skip-lock-tables', '--default-character-set=utf8mb4', '--', database['NAME']], stdout=subprocess.PIPE, stderr=errors)
                    with gzip.open(destination / 'database.sql.gz', 'wb') as output:
                        shutil.copyfileobj(process.stdout, output)
                    process.stdout.close()
                    if process.wait() != 0:
                        raise CommandError('Database dump failed. An INCOMPLETE backup was retained; no credentials were printed.')
            for label, media in stores.items():
                with tarfile.open(destination / f'{label}.tar.gz', 'w:gz', dereference=False) as archive:
                    archive.add(media, arcname=label, recursive=False)
                    for path in media.rglob('*'):
                        if path.is_symlink() or not path.resolve().is_relative_to(media):
                            raise CommandError('Storage contains a symlink; review it before backing up.')
                        if not (path.is_file() or path.is_dir()):
                            raise CommandError('Unsupported storage entry; backup remains INCOMPLETE.')
                        archive.add(path, arcname=label + '/' + path.relative_to(media).as_posix(), recursive=False)
            digests = {}
            for name in ['database.sql.gz', 'media.tar.gz', 'private_documents.tar.gz']:
                with (destination / name).open('rb') as handle:
                    digests[name] = hashlib.file_digest(handle, 'sha256').hexdigest()
            (destination / 'manifest.json').write_text(json.dumps({'created_utc': datetime.now(timezone.utc).isoformat(), 'sha256': digests,
                'notes': 'Keep the matching code release and private production environment separately. Restore to an isolated database and verify before use.'}, indent=2), encoding='utf-8')
            (destination / 'INCOMPLETE').unlink()
            self.stdout.write(self.style.SUCCESS(f'Backup completed in {destination}. Encrypt and copy it off-host; verify a restore. No environment secrets were archived.'))
        finally:
            if process is not None and process.poll() is None:
                process.kill()
                process.wait()
            os.umask(previous_umask)
