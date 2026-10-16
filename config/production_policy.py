"""Validate production inputs without connecting to a database or exposing secrets."""
import re
from pathlib import Path
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured


def production_settings(env, base_dir):
    def required(name):
        value = env.get(name, '').strip()
        if not value or value.lower().startswith(('replace', 'change-me', 'cpanel_prefix')):
            raise ImproperlyConfigured(f'{name} must be configured privately for production.')
        return value

    def boolean(name, default):
        value = str(env.get(name, str(default))).lower().strip()
        if value not in {'true', 'false', '1', '0'}:
            raise ImproperlyConfigured(f'{name} must be True or False.')
        return value in {'true', '1'}

    secret = required('DJANGO_SECRET_KEY')
    if len(secret) < 50 or len(set(secret)) < 5 or secret.startswith(('django-insecure-', 'development-only-')):
        raise ImproperlyConfigured('DJANGO_SECRET_KEY must be a unique random production secret of at least 50 characters.')
    hosts = [host.strip().lower() for host in required('DJANGO_ALLOWED_HOSTS').split(',') if host.strip()]
    if not hosts or any(len(host) > 253 or any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label) for label in host.split('.')) for host in hosts):
        raise ImproperlyConfigured('DJANGO_ALLOWED_HOSTS must contain exact hostnames without wildcards, ports or URLs.')
    origins = [url.strip() for url in required('DJANGO_CSRF_TRUSTED_ORIGINS').split(',') if url.strip()]
    if not origins:
        raise ImproperlyConfigured('Configure at least one HTTPS CSRF origin.')
    for origin in origins:
        parsed = urlsplit(origin)
        if parsed.scheme != 'https' or parsed.netloc not in hosts or parsed.path or parsed.query or parsed.fragment:
            raise ImproperlyConfigured('CSRF origins must be exact HTTPS origins matching allowed hosts.')
    if required('DJANGO_DB_ENGINE') != 'mysql':
        raise ImproperlyConfigured('Production requires DJANGO_DB_ENGINE=mysql; SQLite fallback is disabled.')
    for key in ('DB_NAME', 'DB_USER', 'DB_PASSWORD'):
        required(key)
    if not boolean('DJANGO_SECURE_SSL_REDIRECT', True):
        raise ImproperlyConfigured('Production requires DJANGO_SECURE_SSL_REDIRECT=True. Configure trusted proxy HTTPS detection if needed.')
    try:
        hsts = int(env.get('DJANGO_SECURE_HSTS_SECONDS', '3600'))
        port = int(env.get('DB_PORT', '3306'))
        age = int(env.get('DB_CONN_MAX_AGE', '60'))
    except ValueError:
        raise ImproperlyConfigured('HSTS duration, database port and connection age must be integers.') from None
    if hsts < 1 or not 1 <= port <= 65535 or age < 0:
        raise ImproperlyConfigured('Invalid HSTS duration, database port or connection age.')
    paths = {}
    for name, fallback in [('DJANGO_STATIC_ROOT', base_dir / 'staticfiles'), ('DJANGO_MEDIA_ROOT', base_dir / 'media'), ('DJANGO_PRIVATE_IMPORT_ROOT', base_dir / 'var' / 'private_imports'), ('DJANGO_PRIVATE_DOCUMENT_ROOT', base_dir / 'var' / 'private_documents')]:
        path = Path(env.get(name, str(fallback))).expanduser()
        if not path.is_absolute():
            raise ImproperlyConfigured(f'{name} must be an absolute path.')
        paths[name] = path
    resolved = [path.resolve() for path in paths.values()]
    if any(a == b or a in b.parents or b in a.parents for index, a in enumerate(resolved) for b in resolved[index+1:]):
        raise ImproperlyConfigured('Static, media and private import directories must be separate and non-overlapping.')
    return {
        'DEBUG': False, 'SECRET_KEY': secret, 'ALLOWED_HOSTS': hosts, 'CSRF_TRUSTED_ORIGINS': origins,
        'SECURE_SSL_REDIRECT': True, 'SESSION_COOKIE_SECURE': True, 'CSRF_COOKIE_SECURE': True,
        'SESSION_COOKIE_HTTPONLY': True, 'SESSION_COOKIE_SAMESITE': 'Lax', 'CSRF_COOKIE_SAMESITE': 'Lax',
        'SESSION_COOKIE_DOMAIN': None, 'CSRF_COOKIE_DOMAIN': None,
        'SESSION_COOKIE_NAME': 'smartliving_sessionid', 'CSRF_COOKIE_NAME': 'smartliving_csrftoken',
        'SECURE_HSTS_SECONDS': hsts, 'SECURE_HSTS_INCLUDE_SUBDOMAINS': False, 'SECURE_HSTS_PRELOAD': False,
        'SECURE_PROXY_SSL_HEADER': ('HTTP_X_FORWARDED_PROTO', 'https') if boolean('DJANGO_TRUST_X_FORWARDED_PROTO', False) else None,
        'USE_X_FORWARDED_HOST': False,
        'STATIC_ROOT': paths['DJANGO_STATIC_ROOT'], 'MEDIA_ROOT': paths['DJANGO_MEDIA_ROOT'],
        'PRIVATE_DOCUMENT_ROOT': paths['DJANGO_PRIVATE_DOCUMENT_ROOT'],
        'STORAGES': {
            'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'},
            'import_export': {'BACKEND': 'django.core.files.storage.FileSystemStorage', 'OPTIONS': {'location': paths['DJANGO_PRIVATE_IMPORT_ROOT']}},
        },
        'LOGGING': {'version': 1, 'disable_existing_loggers': False,
                    'formatters': {'production': {'format': '{asctime} {levelname} {name}: {message}', 'style': '{'}},
                    'handlers': {'console': {'class': 'logging.StreamHandler', 'formatter': 'production'}},
                    'loggers': {'django': {'handlers': ['console'], 'level': 'WARNING', 'propagate': False}}},
    }
