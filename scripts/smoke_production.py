"""Read-only HTTPS acceptance probes. Does not submit forms or authenticate."""
import argparse
import ssl
from urllib.error import HTTPError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True, help='Canonical HTTPS origin, e.g. https://smartliving.seas-india.com')
    args = parser.parse_args()
    origin = urlsplit(args.url)
    if origin.scheme != 'https' or not origin.netloc or origin.path not in ('', '/') or origin.username or origin.password or origin.query or origin.fragment:
        parser.error('--url must be a canonical HTTPS origin without credentials or a path.')
    failures = []
    routes = {'/health/live/': {200}, '/health/ready/': {200}, '/': {200}, '/products/': {200}, '/contact/': {200}, '/admin/login/': {200},
              '/.env': {400, 403, 404}, '/manage.py': {403, 404}, '/db.sqlite3': {403, 404}, '/var/private_imports/': {403, 404}}
    for path, expected in routes.items():
        try:
            request = Request(urljoin(args.url, path), headers={'User-Agent': 'SmartLiving-Launch-Check/1.0'})
            try:
                response = urlopen(request, context=ssl.create_default_context(), timeout=20)
            except HTTPError as exc:
                response = exc
            with response:
                final = urlsplit(response.geturl())
                if final.scheme != 'https' or final.netloc != origin.netloc:
                    failures.append(path + ': unexpected redirect origin')
                if response.status not in expected:
                    failures.append(path + ': unexpected HTTP status ' + str(response.status))
                if response.status == 200 and path in {'/', '/admin/login/'}:
                    if not response.headers.get('Strict-Transport-Security') or response.headers.get('X-Content-Type-Options') != 'nosniff':
                        failures.append(path + ': missing production security headers')
                if path.startswith('/health/') and response.status == 200:
                    import json
                    if json.loads(response.read(4096)) != {'status': 'ok'}:
                        failures.append(path + ': invalid health response')
            print(path, 'checked')
        except Exception:
            failures.append(path + ': connection, certificate or response validation failed')
    if failures:
        raise SystemExit('\n'.join(failures))
    print('Read-only HTTPS probes passed. Still verify static/media delivery, login/CSRF, staff workflows and backups/restore manually.')


if __name__ == '__main__':
    main()
