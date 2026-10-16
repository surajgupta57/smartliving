#!/usr/bin/env python3
"""Install the stable deployer for the existing real-directory cPanel layout."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
from datetime import datetime, timezone


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--branch', required=True, help='Reviewed GitHub release branch')
    parser.add_argument('--repository', default='git@github.com:surajgupta57/smartliving.git')
    args = parser.parse_args()
    if os.name != 'posix':
        parser.error('Run on the Linux hosting account in the activated Smart Living virtualenv.')
    from dotenv import dotenv_values, set_key
    source = Path(__file__).resolve().parents[1]
    root = Path.home() / 'apps/smartliving'
    public = Path.home() / 'public_html/smartliving'
    if source != (root / 'current').resolve() or not (source / 'manage.py').is_file():
        parser.error('Upload this release under apps/smartliving/current first.')
    if sys.prefix == sys.base_prefix:
        parser.error('Activate the Smart Living virtualenv first.')
    for name in ('static', 'media'):
        directory = public / name
        if not directory.is_dir() or directory.is_symlink():
            parser.error('Keep the working real public static/media directories before setup.')
    env = root / 'shared/.env'
    origin_env = Path(os.environ.get('DJANGO_ENV_FILE', str(source / '.env')))
    selected = env if env.is_file() else origin_env
    if not selected.is_file() or selected.is_symlink():
        parser.error('A real private production .env is required; migrate panel-only settings into it privately first.')
    values = dotenv_values(selected)
    if not all(values.get(key) for key in ('DJANGO_SECRET_KEY', 'DB_NAME', 'DB_USER', 'DB_PASSWORD')):
        parser.error('Complete the private production .env; secrets were not printed or generated.')
    if values.get('DJANGO_ALLOWED_HOSTS') != 'smartliving.seas-india.com':
        parser.error('Confirm the private environment belongs to Smart Living before setup.')
    if any(part.lower() in {'public_html', 'htdocs', 'httpdocs', 'www'} for part in selected.resolve().parts):
        parser.error('The environment file must be private, outside public roots.')
    for folder in (root, root / 'shared', root / 'deployer', root / 'backups', root / 'logs', root / 'passenger'):
        if folder.is_symlink():
            parser.error('Private deployment control directories must not be symlinks.')
    for name in ('private_imports', 'private_documents'):
        if not (root / 'shared/var' / name).is_dir():
            parser.error('Existing private storage is missing; restore it before setup.')
        key = 'DJANGO_PRIVATE_IMPORT_ROOT' if name == 'private_imports' else 'DJANGO_PRIVATE_DOCUMENT_ROOT'
        existing = Path(values.get(key) or str(source / 'var' / name))
        if existing.resolve() != (root / 'shared/var' / name).resolve():
            parser.error('Existing private storage uses a different path; migrate it with a verified backup before setup.')
    if (public / 'media/.htaccess').is_symlink():
        parser.error('Public media protection must not be a symlink.')
    os.umask(0o077)
    tools = root / 'deployer'
    if (tools / 'deploy.json').exists():
        parser.error('Stable deploy.json already exists. Preserve it and update deploy.py separately; setup is one-time only.')
    for folder in (root / 'shared', tools, root / 'backups', root / 'logs'):
        folder.mkdir(parents=True, exist_ok=True)
    tag = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    shutil.copyfile(selected, root / 'backups' / ('environment-before-automation-' + tag))
    if selected != env:
        shutil.copyfile(selected, env)
    os.chmod(env, 0o600)
    settings = {'DJANGO_ENV': 'production', 'DJANGO_STATIC_ROOT': str(public / 'static'),
                'DJANGO_MEDIA_ROOT': str(public / 'media'),
                'DJANGO_PRIVATE_IMPORT_ROOT': str(root / 'shared/var/private_imports'),
                'DJANGO_PRIVATE_DOCUMENT_ROOT': str(root / 'shared/var/private_documents')}
    for key, value in settings.items():
        set_key(str(env), key, value)
    startup = root / 'passenger/passenger_wsgi.py'
    if startup.is_file():
        shutil.copyfile(startup, root / 'backups' / ('passenger-before-automation-' + tag + '.py'))
    if (public / 'media/.htaccess').is_file():
        shutil.copyfile(public / 'media/.htaccess', root / 'backups' / ('media-protection-before-automation-' + tag))
    shutil.copyfile(source / 'deploy/cpanel/passenger_wsgi.py', startup)
    shutil.copyfile(source / 'deploy/cpanel/media.htaccess', public / 'media/.htaccess')
    os.chmod(public / 'media/.htaccess', 0o644)
    shutil.copyfile(source / 'deploy/deploy.py', tools / 'deploy.py')
    config = {'app_root': str(root), 'public_root': str(public), 'python': sys.executable,
              'repository': args.repository, 'branch': args.branch,
              'ssh_key': str(Path.home() / '.ssh/smartliving_deploy'),
              'origin': 'https://smartliving.seas-india.com', 'drain_seconds': 10, 'health_attempts': 12}
    (tools / 'deploy.json').write_text(json.dumps(config, indent=2) + '\n', encoding='utf-8')
    print('Stable tools installed; existing secret and public uploads preserved.')
    print('Set cPanel DJANGO_ENV_FILE to ' + str(env))
    print('Set SMARTLIVING_PROJECT_ROOT to ' + str(root / 'current'))
    print('Remove duplicated DJANGO_/DB_ overrides from cPanel except those two path selectors, then Restart Smart Living.')
    print('Configure the read-only GitHub deploy key, then follow docs/DEPLOYMENT_AUTOMATION.md for adoption and deployment.')


if __name__ == '__main__':
    main()
