import io
import json
import os
from pathlib import Path
import runpy
import shutil
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from deploy.deploy import Config, Deployer, DeploymentError, NoRedirect, atomic_json, main


ROOT = Path(__file__).resolve().parents[2]


class DeployerTests(SimpleTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name).resolve()
        self.previous = self.root / 'releases/old'
        self.candidate = self.root / 'releases/new'
        for path in [self.previous, self.candidate, self.root / 'shared', self.root / 'passenger', self.root / 'logs']:
            path.mkdir(parents=True, exist_ok=True)
        for release in [self.previous, self.candidate]:
            (release / 'manage.py').touch()
            (release / 'requirements-production.txt').write_text('Django==5.2.18\n')
            (release / 'staticfiles').mkdir()
        self.config = SimpleNamespace(root=self.root, releases=self.root / 'releases', current=self.root / 'current',
            shared=self.root / 'shared', env_file=self.root / 'shared/.env', passenger=self.root / 'passenger',
            marker=self.root / 'maintenance.json', state=self.root / 'deployment-state.json',
            python=Path(sys.executable), origin='https://smartliving.seas-india.com', drain=0, health_attempts=1)
        self.deployer = Deployer(self.config)
        self.events = []

    def pipeline(self, failure=None, allow_dependencies=False, resume=False):
        def event(name):
            self.events.append(name)
            if name == failure:
                raise DeploymentError('Injected failure')
        def manage(release, *arguments):
            event('manage:' + ' '.join(arguments))
            return ''
        with patch.object(self.deployer, 'active', return_value=self.previous), \
             patch.object(self.deployer, 'environment', return_value={}), \
             patch.object(self.deployer, 'checkout', side_effect=lambda: (self.candidate, 'a' * 40)), \
             patch.object(self.deployer, 'health', side_effect=lambda *args: event('health')), \
             patch.object(self.deployer, 'backup', side_effect=lambda release: event('backup')), \
             patch.object(self.deployer, 'manage', side_effect=manage), \
             patch.object(self.deployer, 'run', side_effect=lambda *args, **kwargs: event('pip')), \
             patch.object(self.deployer, 'verify_public_static', side_effect=lambda *args: event('asset-check')), \
             patch.object(self.deployer, 'swap', side_effect=lambda target: event('swap')), \
             patch.object(self.deployer, 'restart', side_effect=lambda: event('restart')):
            self.deployer.deploy(allow_dependencies, resume)

    def test_success_orders_backup_migrations_activation_and_checks(self):
        (self.previous / 'staticfiles/old-hashed.css').write_text('old public asset')
        self.pipeline()
        self.assertLess(self.events.index('backup'), self.events.index('pip'))
        self.assertLess(self.events.index('backup'), self.events.index('manage:migrate --noinput'))
        self.assertLess(self.events.index('manage:migrate --check'), self.events.index('swap'))
        self.assertLess(self.events.index('manage:collectstatic --noinput'), self.events.index('swap'))
        self.assertLess(self.events.index('swap'), self.events.index('restart'))
        self.assertFalse(self.config.marker.exists())
        self.assertEqual(json.loads(self.config.state.read_text())['status'], 'success')
        self.assertFalse(any('loaddata' in event for event in self.events))
        self.assertEqual((self.candidate / 'staticfiles/old-hashed.css').read_text(), 'old public asset')

    def test_pre_migration_failure_keeps_old_code_and_reopens(self):
        with self.assertRaises(DeploymentError):
            self.pipeline(failure='backup')
        self.assertFalse(self.config.marker.exists())
        self.assertNotIn('swap', self.events)
        self.assertNotIn('manage:migrate --noinput', self.events)

    def test_migration_failure_retains_gate_without_restoring_database(self):
        with self.assertRaises(DeploymentError):
            self.pipeline(failure='manage:migrate --noinput')
        self.assertTrue(self.config.marker.exists())
        self.assertTrue(json.loads(self.config.state.read_text())['migration_started'])
        self.assertNotIn('swap', self.events)
        self.assertFalse(any('restore' in event for event in self.events))

    def test_changed_dependencies_require_explicit_flag_before_maintenance(self):
        (self.candidate / 'requirements-production.txt').write_text('Django==5.2.19\n')
        with self.assertRaisesRegex(DeploymentError, 'dependencies changed'):
            self.pipeline()
        self.assertFalse(self.config.marker.exists())
        self.assertNotIn('backup', self.events)

    def test_failed_dependency_change_stays_closed(self):
        (self.candidate / 'requirements-production.txt').write_text('Django==5.2.19\n')
        with self.assertRaises(DeploymentError):
            self.pipeline(failure='pip', allow_dependencies=True)
        self.assertTrue(self.config.marker.exists())
        self.assertNotIn('manage:migrate --noinput', self.events)

    def test_resume_requires_review_and_retains_original_rollback_target(self):
        atomic_json(self.config.marker, {'token': 'private-token'})
        atomic_json(self.config.state, {'status': 'failed', 'previous': str(self.previous), 'migration_started': True})
        with self.assertRaisesRegex(DeploymentError, 'already enabled'):
            self.pipeline()
        self.pipeline(resume=True)
        self.assertEqual(self.events.count('manage:production_check --configuration-only'), 1)
        self.assertEqual(json.loads(self.config.state.read_text())['previous'], str(self.previous))
        self.assertTrue(list((self.root / 'logs').glob('state-*.json')))

    def test_failed_resume_does_not_reopen_prior_uncertain_schema(self):
        atomic_json(self.config.marker, {'token': 'private-token'})
        with self.assertRaises(DeploymentError):
            self.pipeline(failure='backup', resume=True)
        self.assertTrue(self.config.marker.exists())

    def test_rollback_requires_schema_acknowledgement_and_rejects_outside_release(self):
        with self.assertRaisesRegex(DeploymentError, 'schema compatibility'):
            self.deployer.rollback()
        atomic_json(self.config.state, {'previous': str(self.root / 'outside')})
        with self.assertRaisesRegex(DeploymentError, 'valid previous'):
            self.deployer.rollback(schema_compatible=True)
        self.assertFalse(self.config.marker.exists())

    def test_swap_refuses_external_target(self):
        with self.assertRaises(DeploymentError):
            self.deployer.swap(self.root / 'shared')

    def test_public_static_changes_only_public_tree(self):
        assets = self.candidate / 'staticfiles/css'
        assets.mkdir()
        (assets / 'site.css').write_text('body{}')
        (self.candidate / 'private.txt').write_text('private')
        before = (self.candidate / 'private.txt').stat().st_mode
        self.deployer.public_static(self.candidate)
        self.assertEqual(before, (self.candidate / 'private.txt').stat().st_mode)

    def test_failed_command_redacts_secrets_in_private_log(self):
        self.deployer.log = self.root / 'logs/deploy-test.log'
        self.deployer.redactions = ['test-private-password', 'test-private-key']
        result = SimpleNamespace(returncode=1, stdout='test-private-password', stderr='test-private-key')
        with patch('deploy.deploy.subprocess.run', return_value=result):
            with self.assertRaises(DeploymentError):
                self.deployer.run(['example-command'])
        text = self.deployer.log.read_text()
        self.assertNotIn('test-private-password', text)
        self.assertNotIn('test-private-key', text)
        self.assertIn('[REDACTED]', text)

    def enable_public_layout(self):
        self.config.public_root = self.root / 'public_html/smartliving'
        for name in ('static', 'media'):
            (self.config.public_root / name).mkdir(parents=True)

    def test_public_layout_publishes_before_activation_and_preserves_uploads(self):
        self.enable_public_layout()
        media = self.config.public_root / 'media/upload.webp'
        media.write_bytes(b'customer upload')
        (self.config.public_root / 'static/old-hash.css').write_text('old')
        (self.candidate / 'staticfiles/site.css').write_text('new')
        original = self.deployer.publish_static
        def publish(release):
            self.events.append('publish')
            original(release)
        with patch.object(self.deployer, 'publish_static', side_effect=publish):
            self.pipeline()
        self.assertLess(self.events.index('publish'), self.events.index('swap'))
        self.assertEqual((self.config.public_root / 'static/site.css').read_text(), 'new')
        self.assertEqual((self.config.public_root / 'static/old-hash.css').read_text(), 'old')
        self.assertEqual(media.read_bytes(), b'customer upload')

    def test_public_static_rejects_symlink_before_any_public_write(self):
        self.enable_public_layout()
        (self.candidate / 'staticfiles/site.css').write_text('new')
        outside = self.root / 'outside.css'
        outside.write_text('private')
        try:
            (self.config.public_root / 'static/site.css').symlink_to(outside)
        except OSError:
            self.skipTest('Symlink creation requires Windows permission')
        with self.assertRaisesRegex(DeploymentError, 'symlinks'):
            self.deployer.publish_static(self.candidate)
        self.assertEqual(outside.read_text(), 'private')

    def test_public_environment_validates_permanent_roots_but_stages_candidate_static(self):
        self.enable_public_layout()
        values = {'DJANGO_MEDIA_ROOT': str(self.config.public_root / 'media'),
                  'DJANGO_STATIC_ROOT': str(self.config.public_root / 'static'),
                  'DJANGO_PRIVATE_IMPORT_ROOT': str(self.config.shared / 'var/private_imports'),
                  'DJANGO_PRIVATE_DOCUMENT_ROOT': str(self.config.shared / 'var/private_documents'),
                  'DJANGO_ALLOWED_HOSTS': 'smartliving.seas-india.com'}
        with patch('deploy.deploy.subprocess.run', return_value=SimpleNamespace(returncode=0, stdout=json.dumps(values))):
            env = self.deployer.environment(self.candidate)
        self.assertEqual(env['DJANGO_STATIC_ROOT'], str(self.candidate / 'staticfiles'))
        self.assertEqual(env['DJANGO_ENV_FILE'], str(self.config.env_file))
        values['DJANGO_MEDIA_ROOT'] = str(self.config.shared / 'media')
        with patch('deploy.deploy.subprocess.run', return_value=SimpleNamespace(returncode=0, stdout=json.dumps(values))):
            with self.assertRaisesRegex(DeploymentError, 'DJANGO_MEDIA_ROOT'):
                self.deployer.environment(self.candidate)

    def test_publication_failure_keeps_maintenance_and_old_code(self):
        with patch.object(self.deployer, 'publish_static', side_effect=DeploymentError('disk full')):
            with self.assertRaises(DeploymentError):
                self.pipeline()
        self.assertTrue(self.config.marker.exists())
        self.assertNotIn('swap', self.events)

    def test_same_commit_skips_maintenance_and_database_work(self):
        atomic_json(self.previous / 'deployment-manifest.json', {'commit': 'a' * 40})
        self.pipeline()
        self.assertNotIn('backup', self.events)
        self.assertNotIn('manage:migrate --noinput', self.events)
        self.assertFalse(self.config.marker.exists())

    def test_public_asset_verification_rejects_error_html_and_accepts_exact_css(self):
        from unittest.mock import MagicMock
        self.enable_public_layout()
        (self.candidate / 'staticfiles/site.abc.css').write_bytes(b'body{}')
        atomic_json(self.candidate / 'staticfiles/staticfiles.json', {'paths': {'css/site.css': 'site.abc.css'}})
        opener = MagicMock()
        response = opener.open.return_value.__enter__.return_value
        response.status = 200
        response.read.return_value = b'<html>Forbidden</html>'
        with patch('deploy.deploy.build_opener', return_value=opener):
            with self.assertRaisesRegex(DeploymentError, 'stylesheet verification'):
                self.deployer.verify_public_static(self.candidate)
            response.read.return_value = b'body{}'
            self.deployer.verify_public_static(self.candidate)

    def test_public_adoption_snapshots_served_static_without_moving_uploads(self):
        self.enable_public_layout()
        current = self.config.current
        current.mkdir()
        (current / 'manage.py').touch()
        (self.config.public_root / 'static/live.css').write_text('live')
        (self.config.public_root / 'media/upload.webp').write_bytes(b'upload')
        with patch.object(self.deployer, 'environment', return_value={}), \
             patch.object(self.deployer, 'health'), patch.object(self.deployer, 'backup'), \
             patch.object(self.deployer, 'swap'), patch.object(self.deployer, 'restart'):
            self.deployer.adopt()
        baseline = next(self.config.releases.glob('manual-*'))
        self.assertEqual((baseline / 'staticfiles/live.css').read_text(), 'live')
        self.assertEqual((self.config.public_root / 'static/live.css').read_text(), 'live')
        self.assertEqual((self.config.public_root / 'media/upload.webp').read_bytes(), b'upload')
        self.assertFalse(self.config.marker.exists())

    def test_rollback_publishes_previous_assets_before_switching_code(self):
        atomic_json(self.config.state, {'previous': str(self.previous)})
        with patch.object(self.deployer, 'active', return_value=self.candidate), \
             patch.object(self.deployer, 'backup'), patch.object(self.deployer, 'manage'), \
             patch.object(self.deployer, 'health'), patch.object(self.deployer, 'restart'), \
             patch.object(self.deployer, 'publish_static', side_effect=lambda r: self.events.append(('publish', r))), \
             patch.object(self.deployer, 'verify_public_static', side_effect=lambda r: self.events.append(('verify', r))), \
             patch.object(self.deployer, 'swap', side_effect=lambda r: self.events.append(('swap', r))):
            self.deployer.rollback(schema_compatible=True)
        self.assertEqual(self.events, [('publish', self.previous), ('verify', self.previous), ('swap', self.previous)])
        self.assertFalse(self.config.marker.exists())

    def test_dry_run_and_status_do_not_execute_commands_or_create_files(self):
        before = sorted(str(path.relative_to(self.root)) for path in self.root.rglob('*'))
        for argument in ['--dry-run', '--status']:
            with patch('deploy.deploy.Config', return_value=self.config), \
                 patch('deploy.deploy.subprocess.run') as run, patch('sys.stdout', new_callable=io.StringIO):
                self.assertEqual(main([argument]), 0)
                run.assert_not_called()
        after = sorted(str(path.relative_to(self.root)) for path in self.root.rglob('*'))
        self.assertEqual(before, after)

    def test_runtime_environment_clears_stale_db_overrides_and_hides_secrets(self):
        values = {'DJANGO_MEDIA_ROOT': str(self.config.shared / 'media'),
                  'DJANGO_PRIVATE_IMPORT_ROOT': str(self.config.shared / 'var/private_imports'),
                  'DJANGO_PRIVATE_DOCUMENT_ROOT': str(self.config.shared / 'var/private_documents'),
                  'DJANGO_STATIC_ROOT': str(self.config.current / 'staticfiles'),
                  'DJANGO_ALLOWED_HOSTS': 'smartliving.seas-india.com', 'DB_PASSWORD': 'private-test-password'}
        result = SimpleNamespace(returncode=0, stdout=json.dumps(values))
        with patch('deploy.deploy.subprocess.run', return_value=result), \
             patch.dict(os.environ, {'DB_NAME': 'wrong-seas-db', 'DJANGO_DEBUG': 'True', 'GIT_DIR': '/wrong/seas/.git', 'PYTHONPATH': '/wrong/seas'}):
            env = self.deployer.environment(self.candidate)
        self.assertNotIn('DB_NAME', env)
        self.assertNotIn('DJANGO_DEBUG', env)
        self.assertNotIn('DB_PASSWORD', env)
        self.assertNotIn('GIT_DIR', env)
        self.assertNotIn('PYTHONPATH', env)
        self.assertEqual(env['DJANGO_STATIC_ROOT'], str(self.candidate / 'staticfiles'))
        self.assertIn('StrictHostKeyChecking=yes', env['GIT_SSH_COMMAND'])
        self.assertIsNone(self.deployer.log)

    def test_health_rejects_wrong_worker_commit_and_redirects(self):
        from unittest.mock import MagicMock
        opener = MagicMock()
        response = opener.open.return_value.__enter__.return_value
        response.status = 200
        response.read.return_value = b'{"status":"ok"}'
        response.headers = {'X-SmartLiving-Deploy-Protocol': '1', 'X-SmartLiving-Release': 'b' * 40}
        with patch('deploy.deploy.build_opener', return_value=opener):
            with self.assertRaisesRegex(DeploymentError, 'readiness/release'):
                self.deployer.health('a' * 40)
            self.deployer.health('b' * 40)
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, '', {}, 'https://other.example'))

    def test_adoption_activation_failure_restores_manual_source(self):
        current = self.config.current
        current.mkdir()
        (current / 'manage.py').touch()
        (current / 'staticfiles').mkdir()
        with patch.object(self.deployer, 'environment', return_value={}), \
             patch.object(self.deployer, 'health'), patch.object(self.deployer, 'backup'), \
             patch.object(self.deployer, 'swap', side_effect=DeploymentError('swap failed')):
            with self.assertRaises(DeploymentError):
                self.deployer.adopt()
        self.assertTrue((current / 'manage.py').is_file())
        self.assertTrue(self.config.marker.exists())

    def test_candidate_rejects_private_files_before_maintenance(self):
        self.config.repository = 'git@github.com:example/smartliving.git'
        self.config.branch = 'main'
        def clone(arguments, **kwargs):
            if arguments[:2] == ['git', 'clone']:
                destination = Path(arguments[-1])
                destination.mkdir()
                for name in ['manage.py', 'requirements-production.txt', 'config/production.py', 'apps/core/management/commands/backup_site.py', '.env']:
                    path = destination / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.touch()
            return 'a' * 40
        with patch.object(self.deployer, 'environment', return_value={}), patch.object(self.deployer, 'run', side_effect=clone):
            with self.assertRaisesRegex(DeploymentError, 'private environment'):
                self.deployer.checkout()
        self.assertFalse(self.config.marker.exists())

    def test_config_rejects_credentials_public_roots_and_placeholders(self):
        self.config.env_file.touch()
        (self.config.passenger / 'passenger_wsgi.py').write_text('SMARTLIVING_DEPLOY_PROTOCOL = "1"')
        values = {'app_root': str(self.root), 'python': sys.executable,
                  'repository': 'git@github.com:example/smartliving.git', 'branch': 'main',
                  'origin': 'https://smartliving.seas-india.com'}
        path = self.root / 'config.json'
        path.write_text(json.dumps(values))
        self.assertEqual(Config(path).root, self.root)
        for change in [{'repository': 'https://secret@github.com/owner/repo.git'},
                       {'app_root': str(self.root / 'public_html')},
                       {'branch': '--upload-pack=bad'}, {'branch': 'main..evil'},
                       {'origin': 'https://user:secret@smartliving.seas-india.com'},
                       {'repository': 'git@github.com:YOUR_OWNER/YOUR_REPOSITORY.git'}]:
            path.write_text(json.dumps({**values, **change}))
            with self.subTest(change=change), self.assertRaises(DeploymentError):
                Config(path)


class PassengerGateTests(SimpleTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.source = self.root / 'current'
        self.source.mkdir()
        (self.source / 'manage.py').touch()
        atomic_json(self.source / 'deployment-manifest.json', {'commit': 'a' * 40})
        passenger = self.root / 'passenger'
        passenger.mkdir()
        startup = passenger / 'passenger_wsgi.py'
        shutil.copyfile(ROOT / 'deploy/cpanel/passenger_wsgi.py', startup)
        def django(environ, start_response):
            start_response('200 OK', [('Content-Type', 'application/json')])
            return [b'{"status":"ok"}']
        with patch.dict(os.environ, {'SMARTLIVING_PROJECT_ROOT': str(self.source)}), \
             patch.object(sys, 'path', list(sys.path)), \
             patch('django.core.wsgi.get_wsgi_application', return_value=django):
            self.module = runpy.run_path(str(startup))

    def request(self, path='/', method='GET', token=''):
        result = {}
        def start_response(status, headers, exc_info=None):
            result.update(status=status, headers=dict(headers))
        result['body'] = b''.join(self.module['application']({
            'PATH_INFO': path, 'REQUEST_METHOD': method, 'HTTP_X_SMARTLIVING_DEPLOY_TOKEN': token}, start_response))
        return result

    def test_maintenance_denies_customer_requests_and_cannot_bypass_to_other_paths(self):
        atomic_json(self.root / 'maintenance.json', {'token': 'test-token'})
        for path, method, token in [('/', 'GET', ''), ('/contact/', 'POST', 'test-token'),
                                    ('/health/ready/', 'GET', ''), ('/health/ready/', 'POST', 'test-token')]:
            result = self.request(path, method, token)
            self.assertEqual(result['status'], '503 Service Unavailable')
            self.assertEqual(result['headers']['Cache-Control'], 'no-store')
        result = self.request('/health/ready/', 'GET', 'test-token')
        self.assertEqual(result['status'], '200 OK')
        self.assertEqual(result['headers']['X-SmartLiving-Release'], 'a' * 40)

    def test_header_identifies_the_worker_loaded_release(self):
        atomic_json(self.source / 'deployment-manifest.json', {'commit': 'b' * 40})
        self.assertEqual(self.request('/health/ready/')['headers']['X-SmartLiving-Release'], 'a' * 40)
        self.assertEqual(self.request('/')['status'], '200 OK')

    def test_corrupt_gate_fails_closed_and_head_has_no_body(self):
        (self.root / 'maintenance.json').write_text('invalid')
        result = self.request('/health/ready/', 'HEAD', 'anything')
        self.assertEqual(result['status'], '503 Service Unavailable')
        self.assertEqual(result['body'], b'')
