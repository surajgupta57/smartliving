from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.contrib.sitemaps import Sitemap
from django.http import HttpResponse
from apps.catalogue.models import Product
from apps.core import health


class ProductSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8
    def items(self): return Product.objects.filter(is_active=True, is_published=True)
    def lastmod(self, obj): return obj.updated_at
from django.views.generic import TemplateView

urlpatterns = [
    path('health/live/', health.live, name='health_live'),
    path('health/ready/', health.ready, name='health_ready'),
    path("admin/", admin.site.urls),
    path("", include("apps.cms.urls")),
    path("", include("apps.catalogue.urls")),
    path("", include("apps.leads.urls")),
    path("privacy-policy/", TemplateView.as_view(template_name="legal/privacy.html"), name="privacy"),
    path("terms/", TemplateView.as_view(template_name="legal/terms.html"), name="terms"),
    path("sitemap.xml", __import__("django.contrib.sitemaps.views", fromlist=["sitemap"]).sitemap, {"sitemaps": {"products": ProductSitemap}}, name="sitemap"),
    path("robots.txt", lambda request: HttpResponse("User-agent: *\nAllow: /\nSitemap: /sitemap.xml\n", content_type="text/plain"), name="robots"),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler403 = "apps.cms.views.error_403"
handler400 = "apps.cms.views.error_400"
handler404 = "apps.cms.views.error_404"
handler500 = "apps.cms.views.error_500"
