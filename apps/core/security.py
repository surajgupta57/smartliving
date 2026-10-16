"""Database-backed abuse limits; forwarded IP headers are deliberately untrusted."""
import time

from django.db.models import F
from django.http import HttpResponse
from django.utils.cache import patch_cache_control
from django.utils.crypto import salted_hmac
from .models import RequestLimit


class AbuseProtectionMiddleware:
    window_seconds = 300
    public_views = {'leads:contact', 'leads:request_quote', 'leads:product_enquiry', 'leads:site_survey'}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        if request.method != 'POST':
            return None
        name = request.resolver_match.view_name
        if name == 'admin:login':
            group, limit = 'login', 20
        elif name in self.public_views:
            group, limit = 'enquiry', 10
        else:
            return None
        now = int(time.time())
        window = now // self.window_seconds
        identity = request.META.get('REMOTE_ADDR', '') or 'unknown'
        key = salted_hmac('smartliving.abuse', f'{group}:{identity}', algorithm='sha256').hexdigest()
        # One atomic conditional UPDATE admits at most `limit` requests per bucket.
        RequestLimit.objects.filter(window__lt=window - 1).delete()
        RequestLimit.objects.get_or_create(key=key, defaults={'window': window})
        RequestLimit.objects.filter(key=key, window__lt=window).update(window=window, attempts=0)
        admitted = RequestLimit.objects.filter(key=key, window=window, attempts__lt=limit).update(attempts=F('attempts') + 1)
        if admitted:
            return None
        response = HttpResponse('Too many attempts. Please wait a few minutes and try again.', status=429, content_type='text/plain')
        response['Retry-After'] = str(self.window_seconds - now % self.window_seconds)
        patch_cache_control(response, no_store=True, private=True)
        return response
