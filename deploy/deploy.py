#!/usr/bin/env python3
"""One-command GitHub updates for an already configured Smart Living cPanel app."""
from __future__ import annotations

import argparse
import hashlib
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import shutil
import subprocess
import sys
import time
from urllib.parse import urlsplit, quote
from urllib.request import Request, HTTPRedirectHandler, build_opener, HTTPSHandler
import ssl


class DeploymentError(Exception):
    pass


def stamp():
    return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')


def atomic_json(path, value):
    temporary = path.with_name(path.name + '.next')
    with temporary.open('w', encoding='utf-8') as handle:
        json.dump(value, handle, indent=2)
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)


def read_json(path, default=None):
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else default


def private(path):
    if not path.is_absolute() or any(part.lower() in {'public_html', 'htdocs', 'httpdocs', 'www'} for part in path.parts):
        raise DeploymentError('Use absolute private paths outside public document roots.')
    return path


class Config:
    def __init__(self, path):
        values = read_json(path)
        if not isinstance(values, dict):
            raise DeploymentError('Create the private deploy.json from deploy.example.json first.')
        try:
            self.root = private(Path(values['app_root'])).resolve()
            self.python = Path(values['python'])
            self.repository = values['repository']
            self.branch = values['branch']
            self.origin = values['origin']
            self.drain = int(values.get('drain_seconds', 10))
            self.health_attempts = int(values.get('health_attempts', 12))
        except (KeyError, TypeError, ValueError) as exc:
            raise DeploymentError('Invalid deploy.json fields.') from exc
        if not self.python.is_absolute() or not self.python.is_file():
            raise DeploymentError('Set python to this application virtualenv interpreter.')
        if not re.fullmatch(r'git@github\.com:[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\.git', self.repository):
            raise DeploymentError('Use a GitHub SSH URL, without credentials/tokens: git@github.com:OWNER/REPO.git')
        if 'YOUR_' in self.repository or 'ACTUAL_ACCOUNT' in str(self.root):
            raise DeploymentError('Replace all example account/repository values.')
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_./-]*', self.branch) or '..' in self.branch or self.branch.endswith(('/', '.')):
            raise DeploymentError('Invalid Git branch.')
        origin = urlsplit(self.origin)
        if origin.scheme != 'https' or not origin.hostname or origin.username or origin.password or origin.path or origin.query or origin.fragment:
            raise DeploymentError('origin must be an HTTPS origin without a trailing slash or credentials.')
        if not 0 <= self.drain <= 60 or not 1 <= self.health_attempts <= 30:
            raise DeploymentError('Invalid drain_seconds or health_attempts.')
        self.current = self.root / 'current'
        self.public_root = None
        if values.get('public_root'):
            public_root = Path(values['public_root'])
            if not public_root.is_absolute() or public_root.resolve() != public_root or not public_root.is_dir():
                raise DeploymentError('public_root must be an existing real absolute document root.')
            if public_root == self.root or public_root in self.root.parents or self.root in public_root.parents:
                raise DeploymentError('Public and private application roots must be separate.')
            for name in ('static', 'media'):
                directory = public_root / name
                if not directory.is_dir() or directory.is_symlink():
                    raise DeploymentError('public_root/static and media must already be real directories; preserve existing uploads.')
            if not (public_root / 'media/.htaccess').is_file():
                raise DeploymentError('Install the public media protection .htaccess before deploying.')
            self.public_root = public_root
        self.ssh_key = private(Path(values['ssh_key'])).resolve() if values.get('ssh_key') else None
        if self.ssh_key and not self.ssh_key.is_file():
            raise DeploymentError('ssh_key must name the existing private Smart Living deploy key.')
        self.releases = self.root / 'releases'
        self.shared = self.root / 'shared'
        self.env_file = self.shared / '.env'
        self.passenger = self.root / 'passenger'
        self.marker = self.root / 'maintenance.json'
        self.state = self.root / 'deployment-state.json'
        for path in [self.root, self.releases, self.shared, self.passenger]:
            private(path.resolve())
            if path != self.root and path.resolve() != path:
                raise DeploymentError('Deployment control/shared directories must not be symlinks.')
        if not self.env_file.is_file() or self.env_file.is_symlink():
            raise DeploymentError('Missing shared/.env; complete initial production setup first.')
        bootstrap = self.passenger / 'passenger_wsgi.py'
        if not bootstrap.is_file() or 'SMARTLIVING_DEPLOY_PROTOCOL = "1"' not in bootstrap.read_text(encoding='utf-8'):
            raise DeploymentError('Install the new maintenance-aware Passenger bootstrap first.')


@contextmanager
def deployment_lock(root):
    if os.name != 'posix':
        raise DeploymentError('Run deployment on the Linux hosting server, not on Windows.')
    import fcntl
    with (root / 'deployment.lock').open('a') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise DeploymentError('Another deployment is running.') from exc
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Deployer:
    def __init__(self, config):
        self.c = config
        self.log = None
        self.token = ''
        self.redactions = []

    def note(self, message):
        print(message, flush=True)
        if self.log:
            with self.log.open('a', encoding='utf-8') as handle:
                handle.write(message + '\n')

    def run(self, arguments, cwd=None, env=None):
        try:
            result = subprocess.run([str(arg) for arg in arguments], cwd=cwd, env=env,
                                    text=True, encoding='utf-8', errors='replace', capture_output=True,
                                    timeout=1800, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise DeploymentError('Command could not finish; inspect the private deployment log.') from exc
        if self.log:
            output = result.stdout + result.stderr
            for value in self.redactions:
                if value:
                    output = output.replace(value, '[REDACTED]')
            with self.log.open('a', encoding='utf-8') as handle:
                handle.write(output + '\n')
        if result.returncode:
            raise DeploymentError('Command failed; inspect the private deployment log. No further stage was run.')
        return result.stdout.strip()

    def environment(self, release):
        # Parse with the app interpreter, avoiding a dependency for the deploy CLI.
        # Never pass the private parsed configuration through command logging.
        result = subprocess.run([str(self.c.python), '-c',
                                 'import json,sys; from dotenv import dotenv_values; print(json.dumps(dict(dotenv_values(sys.argv[1]))))',
                                 str(self.c.env_file)], capture_output=True, text=True, encoding='utf-8', timeout=30)
        if result.returncode:
            raise DeploymentError('Cannot read shared/.env using the application interpreter.')
        values = json.loads(result.stdout)
        self.redactions = [value for key, value in values.items() if value and any(word in key for word in ('PASSWORD', 'SECRET', 'TOKEN', 'KEY'))]
        public_root = getattr(self.c, 'public_root', None)
        expected = {'DJANGO_MEDIA_ROOT': public_root / 'media' if public_root else self.c.shared / 'media',
                    'DJANGO_PRIVATE_IMPORT_ROOT': self.c.shared / 'var/private_imports',
                    'DJANGO_PRIVATE_DOCUMENT_ROOT': self.c.shared / 'var/private_documents',
                    'DJANGO_STATIC_ROOT': public_root / 'static' if public_root else self.c.current / 'staticfiles'}
        for key, path in expected.items():
            if values.get(key) != str(path):
                raise DeploymentError(f'Set {key} to the exact deployer layout in shared/.env; see deploy/README.md.')
        if values.get('DJANGO_ALLOWED_HOSTS') != urlsplit(self.c.origin).hostname:
            raise DeploymentError('The deployment origin must match the exact host in shared/.env.')
        # Discard inherited Django/database overrides for commands; use one settings source.
        env = {key: value for key, value in os.environ.items()
               if not key.startswith(('DJANGO_', 'DB_', 'GIT_')) and key not in {'PYTHONPATH', 'PYTHONHOME'}}
        ssh = 'ssh -o BatchMode=yes -o StrictHostKeyChecking=yes'
        if getattr(self.c, 'ssh_key', None):
            ssh += ' -o IdentitiesOnly=yes -i ' + shlex.quote(str(self.c.ssh_key))
        env.update({'DJANGO_ENV_FILE': str(self.c.env_file), 'DJANGO_SETTINGS_MODULE': 'config.production',
                    'DJANGO_STATIC_ROOT': str(release / 'staticfiles'), 'PYTHONUTF8': '1',
                    'GIT_TERMINAL_PROMPT': '0', 'GIT_SSH_COMMAND': ssh})
        return env

    def manage(self, release, *args):
        self.note('Django: ' + ' '.join(args))
        return self.run([self.c.python, release / 'manage.py', *args, '--settings=config.production'],
                        cwd=release, env=self.environment(release))

    def active(self):
        current = self.c.current
        if not current.is_symlink():
            raise DeploymentError('current must be a managed release symlink. Run --adopt-current once for the manual installation.')
        target = current.resolve()
        if target.parent != self.c.releases or not (target / 'manage.py').is_file():
            raise DeploymentError('current must point to a release directly inside this app releases/ directory.')
        return target

    def revision(self, release):
        return read_json(release / 'deployment-manifest.json', {}).get('commit', 'manual')

    def health(self, commit=None):
        opener = build_opener(NoRedirect(), HTTPSHandler(context=ssl.create_default_context()))
        for attempt in range(self.c.health_attempts):
            try:
                request = Request(self.c.origin + '/health/ready/', headers={
                    'Cache-Control': 'no-cache', 'X-SmartLiving-Deploy-Token': self.token,
                    'User-Agent': 'SmartLiving-Deploy/1'})
                with opener.open(request, timeout=10) as response:
                    valid = (response.status == 200 and json.loads(response.read(4096)) == {'status': 'ok'}
                             and response.headers.get('X-SmartLiving-Deploy-Protocol') == '1')
                    if commit is not None:
                        valid = valid and response.headers.get('X-SmartLiving-Release') == commit
                    if valid:
                        return
            except Exception:
                pass
            if attempt + 1 < self.c.health_attempts:
                time.sleep(2)
        raise DeploymentError('HTTPS readiness/release check failed; verify DNS, TLS and Passenger restart. Maintenance stays enabled if a deployment started.')

    def maintenance(self, resume=False):
        if self.c.marker.exists():
            if not resume:
                raise DeploymentError('Maintenance is already enabled. Inspect deployment-state.json and use --resume after reviewing the failure.')
            self.token = read_json(self.c.marker)['token']
        else:
            self.token = secrets.token_urlsafe(32)
            atomic_json(self.c.marker, {'token': self.token, 'started': stamp()})
        self.note('Maintenance enabled; waiting for existing requests to drain.')
        time.sleep(self.c.drain)

    def restart(self):
        directory = self.c.passenger / 'tmp'
        directory.mkdir(exist_ok=True)
        (directory / 'restart.txt').touch()
        os.utime(self.c.passenger / 'passenger_wsgi.py', None)

    def swap(self, target):
        if target.parent != self.c.releases or target.resolve() != target or not target.is_dir():
            raise DeploymentError('Refusing an activation outside this application releases directory.')
        temporary = self.c.root / '.current.next'
        if temporary.exists() or temporary.is_symlink():
            raise DeploymentError('An interrupted activation marker exists; inspect .current.next before retrying.')
        temporary.symlink_to(target, target_is_directory=True)
        os.replace(temporary, self.c.current)

    def backup(self, release):
        self.note('Backing up MySQL, media and private documents.')
        self.manage(release, 'backup_site', '--output-dir', str(self.c.root / 'backups'))

    def prepare(self):
        for directory in [self.c.releases, self.c.root / 'logs', self.c.root / 'backups']:
            directory.mkdir(exist_ok=True)
        self.log = self.c.root / 'logs' / f'deploy-{stamp()}.log'

    def public_static(self, release):
        """Only collected public assets get world-read access; source stays private."""
        static = release / 'staticfiles'
        if not static.is_dir() or static.is_symlink():
            raise DeploymentError('Missing or unsafe collected static directory.')
        if not getattr(self.c, 'public_root', None):
            os.chmod(self.c.releases, 0o711)
            os.chmod(release, 0o711)
        os.chmod(static, 0o755)
        for path in static.rglob('*'):
            if path.is_symlink():
                raise DeploymentError('Collected static contains a symlink.')
            os.chmod(path, 0o755 if path.is_dir() else 0o644)

    def publish_static(self, release):
        """Publish staged assets to real public directories without deleting old hashes."""
        public_root = getattr(self.c, 'public_root', None)
        if not public_root:
            return
        source = release / 'staticfiles'
        target = public_root / 'static'
        # Check both complete trees before any write, including dangling symlinks.
        for tree in (source, target):
            if not tree.is_dir() or tree.is_symlink() or any(p.is_symlink() for p in tree.rglob('*')):
                raise DeploymentError('Static publication refuses missing directories or symlinks.')
        for path in sorted(source.rglob('*'), key=lambda p: (len(p.parts), str(p))):
            destination = target / path.relative_to(source)
            if path.is_dir():
                destination.mkdir(exist_ok=True)
                os.chmod(destination, 0o755)
            else:
                temporary = destination.with_name(destination.name + '.deploy-next')
                if temporary.exists() or temporary.is_symlink():
                    raise DeploymentError('Interrupted static publication file exists; inspect it before resuming.')
                try:
                    with path.open('rb') as incoming, temporary.open('xb') as outgoing:
                        shutil.copyfileobj(incoming, outgoing)
                    os.chmod(temporary, 0o644)
                    os.replace(temporary, destination)
                finally:
                    if temporary.is_file() and not temporary.is_symlink():
                        temporary.unlink()

    def verify_public_static(self, release):
        if not getattr(self.c, 'public_root', None):
            return
        static = release / 'staticfiles'
        name = read_json(static / 'staticfiles.json', {}).get('paths', {}).get('css/site.css')
        if not name or not (static / name).is_file() or not (static / name).resolve().is_relative_to(static.resolve()):
            raise DeploymentError('Missing or invalid collected main stylesheet in the static manifest.')
        expected = hashlib.sha256((static / name).read_bytes()).digest()
        opener = build_opener(NoRedirect(), HTTPSHandler(context=ssl.create_default_context()))
        try:
            request = Request(self.c.origin + '/static/' + quote(name), headers={'Cache-Control': 'no-cache'})
            with opener.open(request, timeout=20) as response:
                if response.status != 200 or hashlib.sha256(response.read(4 * 1024 * 1024)).digest() != expected:
                    raise DeploymentError('Published stylesheet content does not match the candidate.')
        except Exception as exc:
            raise DeploymentError('Public stylesheet verification failed; check Apache permissions and CDN response. Maintenance retained.') from exc

    def retain_static(self, previous, release):
        source = previous / 'staticfiles'
        if not source.is_dir() or source.is_symlink() or any(path.is_symlink() for path in source.rglob('*')):
            raise DeploymentError('The previous release must have a real staticfiles directory without symlinks.')
        # Keep hashed assets referenced by already-open/cached pages after activation.
        shutil.copytree(source, release / 'staticfiles', dirs_exist_ok=True)

    def checkout(self):
        release = self.c.releases / stamp()
        git_env = self.environment(self.c.current.resolve())
        self.run(['git', 'clone', '--depth', '1', '--single-branch', '--branch', self.c.branch,
                  '--', self.c.repository, release], env=git_env)
        commit = self.run(['git', 'rev-parse', 'HEAD'], cwd=release, env=git_env)
        if not re.fullmatch('[0-9a-f]{40,64}', commit):
            raise DeploymentError('Git did not return a valid commit ID.')
        self.run(['git', 'checkout', '--detach', commit], cwd=release, env=git_env)
        required = ['manage.py', 'requirements-production.txt', 'config/production.py', 'apps/core/management/commands/backup_site.py']
        if not all((release / name).is_file() for name in required):
            raise DeploymentError('Repository is missing required Smart Living deployment files.')
        for path in release.rglob('*'):
            parts = path.relative_to(release).parts
            if '.git' in parts:
                continue
            if path.is_symlink() or parts[0] in {'media', 'staticfiles', 'var', '.venv'} or path.suffix in {'.sqlite3', '.sql'}:
                raise DeploymentError('Git release contains storage, a database or a symlink; remove it from the repository before deploying.')
            if path.name in {'.env', 'deploy.json'} or (path.name.startswith('.env.') and not path.name.endswith('.example')):
                raise DeploymentError('Git release contains a private environment/configuration file.')
        atomic_json(release / 'deployment-manifest.json', {'commit': commit, 'created': stamp()})
        return release, commit

    def adopt(self, resume=False):
        current = self.c.current
        if current.is_symlink():
            if self.c.marker.exists() and resume:
                if read_json(self.c.state, {}).get('operation') != 'adoption':
                    raise DeploymentError('This gate is not from adoption. Review the failed deployment and use its documented recovery path.')
                self.token = read_json(self.c.marker)['token']
                self.manage(self.active(), 'production_check')
                self.restart()
                self.health(self.revision(self.active()))
                self.c.marker.unlink()
                self.note('Adoption readiness verified; maintenance removed.')
                return
            self.note('current is already a managed symlink; no adoption needed.')
            return
        if not current.is_dir() or not (current / 'manage.py').is_file():
            raise DeploymentError('Adoption needs the existing manual current/ source directory.')
        self.environment(current)
        if self.c.marker.exists() and resume:
            if read_json(self.c.state, {}).get('operation') != 'adoption':
                raise DeploymentError('The existing maintenance gate is not from adoption.')
            self.token = read_json(self.c.marker)['token']
        self.health('manual')
        atomic_json(self.c.state, {'operation': 'adoption', 'status': 'running', 'migration_started': False})
        self.maintenance(resume)
        self.backup(current)
        static = current / 'staticfiles'
        public_root = getattr(self.c, 'public_root', None)
        if public_root:
            # Snapshot actual served assets, not the stale shared/staticfiles copy.
            if static.is_symlink():
                static.unlink()
            source = public_root / 'static'
            if any(path.is_symlink() for path in source.rglob('*')) or (static.exists() and any(path.is_symlink() for path in static.rglob('*'))):
                raise DeploymentError('Public static contains symlinks; review before adoption.')
            shutil.copytree(source, static, dirs_exist_ok=True)
        elif not static.exists():
            source = self.c.shared / 'staticfiles'
            if not source.is_dir() or any(path.is_symlink() for path in source.rglob('*')):
                raise DeploymentError('Cannot adopt public static files; inspect shared/staticfiles first.')
            shutil.copytree(source, static)
        if static.is_symlink():
            raise DeploymentError('Use a real current/staticfiles directory before adoption; preserve the existing static contents.')
        baseline = self.c.releases / ('manual-' + stamp())
        current.rename(baseline)
        try:
            self.public_static(baseline)
            self.swap(baseline)
        except Exception:
            if not current.exists() and not current.is_symlink():
                baseline.rename(current)
            raise
        self.restart()
        self.health('manual')
        atomic_json(self.c.state, {'operation': 'adoption', 'status': 'adopted', 'active': str(baseline), 'migration_started': False})
        self.c.marker.unlink()
        self.note('Manual release adopted. ' + ('Public static/media directories were preserved.' if public_root else 'Configure /static/ to point to current/staticfiles as documented.'))

    def deploy(self, allow_dependencies=False, resume=False):
        previous = self.active()
        self.environment(previous)
        resumed_gate = self.c.marker.exists()
        if self.c.marker.exists() and not resume:
            raise DeploymentError('Maintenance is already enabled; review the previous failure before --resume.')
        if not self.c.marker.exists():
            self.health(self.revision(previous))
        if not resumed_gate:
            self.manage(previous, 'production_check', '--configuration-only')
        release, commit = self.checkout()
        if not resumed_gate and commit == self.revision(previous):
            self.note('Already running GitHub commit ' + commit + '; no maintenance, migrations or backup needed.')
            return
        changed = (release / 'requirements-production.txt').read_bytes() != (previous / 'requirements-production.txt').read_bytes()
        if changed and not allow_dependencies:
            raise DeploymentError('Production dependencies changed. Review them and rerun with --allow-dependency-change in a maintenance window.')
        self.maintenance(resume)
        state = {'status': 'running', 'previous': str(previous), 'candidate': str(release), 'commit': commit,
                 'migration_started': False, 'dependencies_changed': changed}
        prior_state = read_json(self.c.state, {})
        if prior_state:
            atomic_json(self.c.root / 'logs' / ('state-' + stamp() + '.json'), prior_state)
        if resumed_gate and prior_state.get('status') == 'failed' and prior_state.get('previous'):
            state['previous'] = prior_state['previous']
        atomic_json(self.c.state, state)
        activated = False
        migration_started = False
        dependencies_touched = False
        try:
            self.backup(previous)
            dependencies_touched = changed
            if changed:
                self.note('Installing reviewed changed production dependencies.')
                self.run([self.c.python, '-m', 'pip', 'install', '--disable-pip-version-check', '-r', release / 'requirements-production.txt'],
                         cwd=release, env=self.environment(release))
            self.run([self.c.python, '-m', 'pip', 'check'], cwd=release, env=self.environment(release))
            self.manage(release, 'production_check', '--configuration-only')
            self.manage(release, 'check')
            self.manage(release, 'makemigrations', '--check', '--dry-run')
            self.manage(release, 'migrate', '--plan')
            # Conservatively mark before invocation: an interrupted migration may have committed DDL.
            migration_started = True
            state['migration_started'] = True
            atomic_json(self.c.state, state)
            self.note('Applying committed migrations and collecting this release static files.')
            self.manage(release, 'migrate', '--noinput')
            self.manage(release, 'migrate', '--check')
            self.retain_static(previous, release)
            self.manage(release, 'collectstatic', '--noinput')
            self.public_static(release)
            self.manage(release, 'production_check')
            self.publish_static(release)
            self.verify_public_static(release)
            self.swap(release)
            activated = True
            self.restart()
            self.health(commit)
            state['status'] = 'success'
            atomic_json(self.c.state, state)
            self.c.marker.unlink()
            self.token = ''
            self.health(commit)
            self.note('Deployment successful: ' + commit)
        except Exception:
            # Never restore SQL or reopen old code against potentially changed schema/packages.
            if not self.c.marker.exists():
                self.maintenance()
            state['status'] = 'failed'
            state['activated'] = activated
            atomic_json(self.c.state, state)
            if not resumed_gate and not migration_started and not dependencies_touched:
                self.health(self.revision(previous))
                self.c.marker.unlink()
                self.note('Candidate rejected before migrations; the previous release remains active.')
            else:
                self.note('Maintenance retained. Database/files were NOT restored. Review the log, then --resume or an explicitly compatible --rollback.')
            raise

    def rollback(self, schema_compatible=False):
        if not schema_compatible:
            raise DeploymentError('Review schema compatibility first, then pass --schema-compatible. No database restoration is performed.')
        state = read_json(self.c.state, {})
        previous = Path(state.get('previous', ''))
        if previous.parent != self.c.releases or previous.resolve() != previous or not (previous / 'manage.py').is_file():
            raise DeploymentError('No valid previous managed release is recorded.')
        self.maintenance(resume=True)
        self.backup(self.active())
        self.manage(previous, 'production_check')
        self.publish_static(previous)
        self.verify_public_static(previous)
        self.swap(previous)
        self.restart()
        self.health(self.revision(previous))
        atomic_json(self.c.state, {**state, 'status': 'rolled_back', 'active': str(previous)})
        self.c.marker.unlink()
        self.note('Compatible code rollback completed; database and uploads were preserved.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=Path(__file__).with_name('deploy.json'))
    actions = parser.add_mutually_exclusive_group()
    for action in ['dry-run', 'status', 'health', 'backup', 'adopt-current', 'rollback']:
        actions.add_argument('--' + action, action='store_true')
    parser.add_argument('--allow-dependency-change', action='store_true')
    parser.add_argument('--schema-compatible', action='store_true')
    parser.add_argument('--resume', action='store_true')
    options = parser.parse_args(argv)
    try:
        config = Config(options.config)
        deployer = Deployer(config)
        if options.dry_run:
            print('DRY RUN: configuration paths validated; no Git/network/database/filesystem changes performed.')
            print('Plan: clone GitHub branch -> maintenance/drain -> backup -> dependencies/checks -> migrate -> collectstatic -> preflight -> atomic current swap -> Passenger restart -> exact-release HTTPS readiness -> reopen.')
            return 0
        if options.status:
            print(json.dumps({'active': str(config.current.resolve()), 'maintenance': config.marker.exists(),
                              'last_deployment': read_json(config.state, {})}, indent=2))
            return 0
        if options.health:
            deployer.token = read_json(config.marker, {}).get('token', '')
            deployer.health(deployer.revision(deployer.active()))
            print('HTTPS readiness and active release verified.')
            return 0
        previous_umask = os.umask(0o077)
        try:
            with deployment_lock(config.root):
                deployer.prepare()
                if options.adopt_current:
                    deployer.adopt(options.resume)
                elif options.backup:
                    deployer.backup(deployer.active())
                elif options.rollback:
                    deployer.rollback(options.schema_compatible)
                else:
                    deployer.deploy(options.allow_dependency_change, options.resume)
        finally:
            os.umask(previous_umask)
        return 0
    except Exception as exc:
        if isinstance(exc, DeploymentError):
            print('Deployment stopped: ' + str(exc), file=sys.stderr)
        else:
            print('Deployment stopped unexpectedly. Inspect the private log/state and maintenance status before retrying.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
