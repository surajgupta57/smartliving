from unittest.mock import patch

from django.http import HttpResponse
from django.test import Client, RequestFactory, TestCase
from django.urls import resolve

from .models import RequestLimit
from .security import AbuseProtectionMiddleware


class AbuseProtectionTests(TestCase):
    def setUp(self):
        self.middleware = AbuseProtectionMiddleware(lambda request: HttpResponse('OK'))
        self.factory = RequestFactory()

    def attempt(self, path='/contact/', ip='192.0.2.1', **headers):
        request = self.factory.post(path, REMOTE_ADDR=ip, **headers)
        request.resolver_match = resolve(path)
        return self.middleware.process_view(request, None, (), {})

    def test_public_forms_share_limit_and_other_ips_are_independent(self):
        for index in range(10):
            self.assertIsNone(self.attempt('/contact/' if index % 2 else '/request-quote/'))
        response = self.attempt('/site-survey/')
        self.assertEqual(response.status_code, 429)
        self.assertGreater(int(response['Retry-After']), 0)
        self.assertIn('no-store', response['Cache-Control'])
        self.assertIsNone(self.attempt(ip='192.0.2.2'))
        self.assertNotIn('192.0.2.1', RequestLimit.objects.first().key)

    def test_forwarded_headers_cannot_bypass_limit(self):
        for _ in range(10):
            self.attempt()
        self.assertEqual(self.attempt(HTTP_X_FORWARDED_FOR='192.0.2.99').status_code, 429)

    def test_login_limit_separate_from_enquiries(self):
        for _ in range(20):
            self.assertIsNone(self.attempt('/admin/login/'))
        self.assertEqual(self.attempt('/admin/login/').status_code, 429)
        self.assertIsNone(self.attempt())

    @patch('apps.core.security.time.time')
    def test_window_resets_and_expired_counters_are_removed(self, now):
        now.return_value = 3000
        for _ in range(10):
            self.attempt()
        self.assertEqual(self.attempt().status_code, 429)
        now.return_value = 3300
        self.assertIsNone(self.attempt())
        now.return_value = 4200
        self.assertIsNone(self.attempt(ip='192.0.2.2'))
        self.assertEqual(RequestLimit.objects.count(), 1)

    def test_get_and_staff_mutations_do_not_consume_limits(self):
        request = self.factory.get('/contact/')
        self.assertIsNone(self.middleware.process_view(request, None, (), {}))
        self.assertIsNone(self.attempt('/workspace/enquiries/new/'))
        self.assertFalse(RequestLimit.objects.exists())

    def test_csrf_still_required_and_response_has_browser_policy(self):
        response = Client(enforce_csrf_checks=True).post('/contact/', {})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response['Permissions-Policy'], 'camera=(), microphone=(), geolocation=()')
        self.assertFalse(RequestLimit.objects.exists())
