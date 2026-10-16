from io import StringIO
import secrets
from pathlib import Path
import tempfile
from unittest.mock import patch
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command, CommandError
from django.db import OperationalError
from django.test import Client, RequestFactory, SimpleTestCase, override_settings
from config.production_policy import production_settings
from apps.cms import views


class ProductionPolicyTests(SimpleTestCase):
    def setUp(self):
        self.base=Path(tempfile.gettempdir())/'smartliving-production-policy'
        self.env={'DJANGO_SECRET_KEY':secrets.token_urlsafe(64),'DJANGO_ALLOWED_HOSTS':'smartliving.seas-india.com','DJANGO_CSRF_TRUSTED_ORIGINS':'https://smartliving.seas-india.com','DJANGO_DB_ENGINE':'mysql','DB_NAME':'smartliving','DB_USER':'smartliving_app','DB_PASSWORD':'synthetic-database-password'}

    def test_secure_defaults_and_proxy_is_opt_in(self):
        result=production_settings(self.env,self.base)
        self.assertFalse(result['DEBUG'])
        self.assertTrue(result['SECURE_SSL_REDIRECT'])
        self.assertTrue(result['SESSION_COOKIE_SECURE'])
        self.assertTrue(result['CSRF_COOKIE_SECURE'])
        self.assertEqual(result['SECURE_HSTS_SECONDS'],3600)
        self.assertFalse(result['SECURE_HSTS_INCLUDE_SUBDOMAINS'])
        self.assertFalse(result['SECURE_HSTS_PRELOAD'])
        self.assertIsNone(result['SECURE_PROXY_SSL_HEADER'])
        self.assertEqual(result['SESSION_COOKIE_NAME'],'smartliving_sessionid')
        self.assertIsNone(result['SESSION_COOKIE_DOMAIN'])
        self.env['DJANGO_TRUST_X_FORWARDED_PROTO']='True'
        self.assertEqual(production_settings(self.env,self.base)['SECURE_PROXY_SSL_HEADER'],('HTTP_X_FORWARDED_PROTO','https'))

    def test_missing_and_placeholder_values_fail_without_revealing_secret(self):
        for key in self.env:
            env=self.env.copy();env.pop(key)
            with self.subTest(key=key), self.assertRaises(ImproperlyConfigured) as error:
                production_settings(env,self.base)
            self.assertNotIn(self.env['DJANGO_SECRET_KEY'],str(error.exception))
            self.assertNotIn(self.env['DB_PASSWORD'],str(error.exception))
        for secret in ['development-only-change-before-deployment','x'*70,'replace-with-a-long-random-secret']:
            env={**self.env,'DJANGO_SECRET_KEY':secret}
            with self.assertRaises(ImproperlyConfigured):production_settings(env,self.base)

    def test_wildcards_urls_and_bad_csrf_origins_fail(self):
        for value in ['*','.seas-india.com','https://smartliving.seas-india.com','smartliving.seas-india.com:443','smartliving..com']:
            with self.subTest(host=value),self.assertRaises(ImproperlyConfigured):production_settings({**self.env,'DJANGO_ALLOWED_HOSTS':value},self.base)
        for value in ['http://smartliving.seas-india.com','https://*.seas-india.com','https://another.example','https://smartliving.seas-india.com/path']:
            with self.subTest(origin=value),self.assertRaises(ImproperlyConfigured):production_settings({**self.env,'DJANGO_CSRF_TRUSTED_ORIGINS':value},self.base)

    def test_sqlite_insecure_flags_and_invalid_numbers_are_rejected(self):
        for change in [{'DJANGO_DB_ENGINE':'sqlite'},{'DJANGO_SECURE_SSL_REDIRECT':'False'},{'DJANGO_TRUST_X_FORWARDED_PROTO':'maybe'},{'DJANGO_SECURE_HSTS_SECONDS':'0'},{'DB_PORT':'999999'},{'DB_CONN_MAX_AGE':'-1'}]:
            with self.subTest(change=change),self.assertRaises(ImproperlyConfigured):production_settings({**self.env,**change},self.base)

    def test_public_and_private_paths_cannot_overlap(self):
        for change in [{'DJANGO_PRIVATE_DOCUMENT_ROOT':str(self.base/'media'/'private')},{'DJANGO_STATIC_ROOT':str(self.base/'media')},{'DJANGO_MEDIA_ROOT':'relative/media'}]:
            with self.subTest(change=change),self.assertRaises(ImproperlyConfigured):production_settings({**self.env,**change},self.base)

    def test_preflight_rejects_development_settings(self):
        with self.assertRaises(CommandError):call_command('production_check',stdout=StringIO())


class ProductionResponseTests(SimpleTestCase):
    def test_error_pages_do_not_use_database_or_context_processors(self):
        request=RequestFactory().get('/missing/',HTTP_HOST='invalid.example')
        with patch('apps.core.models.SiteSettings.load',side_effect=AssertionError('Database context must not run')):
            for code in [400,403,404,500]:
                response=getattr(views,'error_'+str(code))(request)
                self.assertEqual(response.status_code,code)
                self.assertNotIn(b'Traceback',response.content)
                self.assertIn(b'noindex',response.content)

    def test_liveness_does_not_query_database_and_supports_head(self):
        client=Client(HTTP_HOST='localhost')
        self.assertEqual(client.get('/health/live/').json(),{'status':'ok'})
        self.assertEqual(client.head('/health/live/').status_code,200)
        self.assertEqual(client.post('/health/live/').status_code,405)

    def test_database_failure_is_generic_and_uncached(self):
        with patch('apps.core.health.connection') as fake_connection:
            fake_connection.cursor.side_effect=OperationalError('private db detail')
            with self.assertLogs('apps.core.health',level='ERROR'):
                response=Client(HTTP_HOST='localhost').get('/health/ready/')
        self.assertEqual(response.status_code,503)
        self.assertEqual(response.json(),{'status':'unavailable'})
        self.assertNotContains(response,'private db detail',status_code=503)
        self.assertIn('no-store',response.headers['Cache-Control'])

    @override_settings(SECURE_SSL_REDIRECT=True,SECURE_HSTS_SECONDS=3600,SECURE_HSTS_INCLUDE_SUBDOMAINS=False,SECURE_HSTS_PRELOAD=False,ALLOWED_HOSTS=['smartliving.seas-india.com'])
    def test_https_redirect_and_security_headers(self):
        client=Client(HTTP_HOST='smartliving.seas-india.com')
        response=client.get('/health/live/')
        self.assertEqual(response.status_code,301)
        self.assertEqual(response['Location'],'https://smartliving.seas-india.com/health/live/')
        secure=client.get('/health/live/',secure=True)
        self.assertEqual(secure['Strict-Transport-Security'],'max-age=3600')
        self.assertEqual(secure['X-Content-Type-Options'],'nosniff')
