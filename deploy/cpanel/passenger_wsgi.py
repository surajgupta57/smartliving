"""Copy to apps/smartliving/passenger/passenger_wsgi.py on the host."""
import os
import sys
from pathlib import Path
import json
import secrets

# Keep this bootstrap in the permanent passenger/ directory, outside releases.
SMARTLIVING_DEPLOY_PROTOCOL = "1"
app_root = Path(__file__).resolve().parent.parent
maintenance_path = app_root / 'maintenance.json'

project_root = Path(os.environ.get('SMARTLIVING_PROJECT_ROOT', str(Path(__file__).resolve().parent.parent / 'current'))).resolve()
if not (project_root / 'manage.py').is_file():
    raise RuntimeError('Set SMARTLIVING_PROJECT_ROOT to the private Smart Living source directory.')
sys.path.insert(0, str(project_root))
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.production'
from django.core.wsgi import get_wsgi_application

django_application = get_wsgi_application()
manifest = project_root / 'deployment-manifest.json'
release_commit = json.loads(manifest.read_text(encoding='utf-8')).get('commit', 'manual') if manifest.is_file() else 'manual'


def application(environ, start_response):
    """Gate new requests during releases, allowing only authenticated health probes."""
    maintenance = maintenance_path.exists()
    permitted = False
    if maintenance and environ.get('PATH_INFO') == '/health/ready/' and environ.get('REQUEST_METHOD') in {'GET', 'HEAD'}:
        try:
            token = json.loads(maintenance_path.read_text(encoding='utf-8'))['token']
            supplied = environ.get('HTTP_X_SMARTLIVING_DEPLOY_TOKEN', '')
            permitted = bool(token) and secrets.compare_digest(token, supplied)
        except (OSError, ValueError, KeyError, TypeError):
            pass
    if maintenance and not permitted:
        body = b'The site is being updated. Please try again shortly.'
        start_response('503 Service Unavailable', [('Content-Type', 'text/plain; charset=utf-8'),
                       ('Content-Length', str(len(body))), ('Retry-After', '60'), ('Cache-Control', 'no-store')])
        return [b'' if environ.get('REQUEST_METHOD') == 'HEAD' else body]

    def response(status, headers, exc_info=None):
        if environ.get('PATH_INFO') == '/health/ready/':
            headers = list(headers) + [('X-SmartLiving-Deploy-Protocol', SMARTLIVING_DEPLOY_PROTOCOL),
                                       ('X-SmartLiving-Release', release_commit)]
        return start_response(status, headers, exc_info)

    return django_application(environ, response)
