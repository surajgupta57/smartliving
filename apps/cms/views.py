from django.shortcuts import get_object_or_404, render
from django.templatetags.static import static
from apps.catalogue.models import Brand, Category
from apps.catalogue.queries import card_products
from .models import ContentPage, FAQ, HomeSection


def home(request):
    fallback_brands = {
        'cp-plus': 'cp-plus-official.png',
        'ezviz': 'ezviz-official.png',
        'shelly': 'shelly-official.svg',
        'sonoff': 'sonoff-official.png',
        'tp-link': 'tp-link-official.svg',
        'zipato': 'zipato-official.png',
    }
    brands = []
    for brand in Brand.objects.filter(is_active=True, is_published=True).only("name", "slug", "logo"):
        if brand.logo:
            brand.carousel_logo_url = brand.logo.url
        elif brand.slug in fallback_brands:
            brand.carousel_logo_url = static(f'images/brands/{fallback_brands[brand.slug]}')
        else:
            continue
        brands.append(brand)
    return render(request, "cms/home.html", {"sections": HomeSection.objects.filter(is_enabled=True), "featured_products": card_products().filter(is_featured=True)[:6], "categories": Category.objects.filter(is_active=True, is_published=True, is_featured=True, parent__isnull=True)[:6], "faqs": FAQ.objects.filter(is_published=True)[:6], "brands": brands})


def listing(request, kind, title):
    return render(request, "cms/content_list.html", {"pages": ContentPage.objects.filter(kind=kind, is_published=True), "title": title, "kind": kind,
        "project_guides": ContentPage.objects.filter(kind='project_guide', is_published=True) if kind == 'project' else ContentPage.objects.none()})


def detail(request, kind, slug):
    kinds = ['project', 'project_guide'] if kind == 'project' else [kind]
    pages = ContentPage.objects.filter(kind__in=kinds, slug=slug, is_published=True)
    page = pages.filter(kind=kind).first() or get_object_or_404(pages)
    return render(request, "cms/content_detail.html", {"page": page})


def technology(request):
    return listing(request, "technology", "Supported technology")


def about(request):
    return render(request, "cms/about.html")


def support(request):
    return render(request, "cms/support.html")


def error_response(code):
    # Do not call context processors, sessions or the database on error paths.
    from django.http import HttpResponse
    from django.template.loader import render_to_string
    return HttpResponse(render_to_string(f'errors/{code}.html'), status=code)


def error_400(request, exception=None): return error_response(400)
def error_403(request, exception=None): return error_response(403)
def error_404(request, exception=None): return error_response(404)
def error_500(request): return error_response(500)
