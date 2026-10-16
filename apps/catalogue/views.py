from urllib.parse import quote
from django.contrib import messages
from django.db.models import Q, Exists, OuterRef, Subquery, Prefetch
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.utils.http import url_has_allowed_host_and_scheme
from apps.core.models import SiteSettings
from django.http import JsonResponse
from django.template.loader import render_to_string
from .search import search_products
from .forms import ProductFilterForm, QuoteItemForm
from .models import Brand, Category, Product, ProductImage, ProductCompatibility
from .taxonomy import CCTV_ROOT, CAMERAS, CAMERA_LEAVES, descendants


def public_products():
    return Product.objects.filter(is_active=True, is_published=True).select_related("brand", "primary_category").prefetch_related("specifications", "images")


def filter_categories(products, slugs):
    category_ids = Category.objects.filter(slug__in=slugs).values("pk")
    additional = Product.additional_categories.through.objects.filter(product_id=OuterRef("pk"), category_id__in=Subquery(category_ids))
    return products.filter(Q(primary_category_id__in=Subquery(category_ids)) | Exists(additional))


def safe_next(request, fallback):
    target = request.POST.get("next", "")
    return target if url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}, require_https=request.is_secure()) else fallback


def product_list(request, category_slug=None, brand_slug=None):
    products = Product.objects.filter(is_active=True, is_published=True).select_related("brand").only(
        "name", "slug", "sku", "model_number", "short_description", "featured_image",
        "price_display_mode", "price", "starting_price", "currency", "is_demo", "is_featured", "is_new", "brand__name",
    ).prefetch_related(Prefetch("images", queryset=ProductImage.objects.filter(is_primary=True).only("product_id", "image", "is_primary")))
    categories = list(Category.objects.filter(is_active=True, is_published=True))
    category_map = {category.slug: category for category in categories}
    initial = {"category": request.GET.get("category", category_slug or ""), "brand": request.GET.get("brand", brand_slug or ""), "q": request.GET.get("q", ""), "availability": request.GET.get("availability", ""), "sort": request.GET.get("sort", "featured")}
    for key in ['product_type', 'camera_technology', 'camera_shape', 'camera_motion', 'camera_connection']:
        initial[key] = request.GET.get(key, '')
    selected = category_map.get(initial['category'])
    cctv_slugs = descendants(category_map[CCTV_ROOT], categories) if CCTV_ROOT in category_map else set()
    show_cctv = initial['category'] in cctv_slugs
    form = ProductFilterForm(initial)
    if form.is_valid():
        data = form.cleaned_data
        if data["q"]:
            products = search_products(products, data["q"])
        if data["category"]:
            slugs = descendants(selected, categories) if selected else {data['category']}
            products = filter_categories(products, slugs)
        if show_cctv:
            filters = []
            if data['product_type']:
                kind = category_map.get(data['product_type'])
                filters.append(descendants(kind, categories) if kind else {data['product_type']})
            if data['product_type'] in ['', CAMERAS]:
                if data['camera_technology'] == 'ip': filters.append({'cctv-ip-cameras', 'wi-fi-and-4g-cameras'})
                if data['camera_technology'] == 'analog': filters.append({'hd-analog-cctv-cameras'})
                for key in ['camera_shape', 'camera_motion', 'camera_connection']:
                    if data[key]: filters.append({data[key]})
            for slugs in filters:
                products = filter_categories(products, slugs)
        if data["brand"]:
            products = products.filter(brand__slug=data["brand"])
        if data["availability"]:
            products = products.filter(stock_status=data["availability"])
        for key, value in request.GET.items():
            if key.startswith("spec_") and value:
                products = products.filter(specifications__name__iexact=key[5:].replace("-", " "), specifications__value__iexact=value)
        ordering = {"name": ("name", "pk"), "price_low": ("price", "display_order", "name", "pk"), "price_high": ("-price", "display_order", "name", "pk")}.get(data["sort"], ("-is_featured", "display_order", "name", "pk"))
        products = products.order_by(*ordering)
    else:
        products = products.none()
    per_page = request.GET.get("per_page", "24")
    per_page = int(per_page) if per_page in {"12", "24", "48"} else 24
    page = Paginator(products, per_page).get_page(request.GET.get("page"))
    query = request.GET.copy()
    query.pop("page", None)
    context = {"products": page, "page": page, "filter_query": query.urlencode(), "form": form, "categories": [category for category in categories if category.parent_id is None], "selected_child": selected if selected and selected.parent_id else None, "show_cctv": show_cctv, "brands": Brand.objects.filter(is_active=True, is_published=True), "per_page": str(per_page)}
    if request.headers.get("X-Catalogue-Live") == "1":
        return JsonResponse({"html": render_to_string("catalogue/_results.html", context, request=request)})
    return render(request, "catalogue/product_list.html", context)


def product_detail(request, slug):
    product = get_object_or_404(public_products(), slug=slug)
    recent = request.session.get("recent_products", [])
    request.session["recent_products"] = ([product.pk] + [pk for pk in recent if pk != product.pk])[:6]
    settings = SiteSettings.load()
    digits = "".join(c for c in settings.whatsapp_number if c.isdigit())
    message = f"Hello, I would like information about {product.name}: {settings.public_url}{product.get_absolute_url()}"
    return render(request, "catalogue/product_detail.html", {"product": product, "compatibility_links": verified_pairings().filter(product=product), "related": public_products().filter(primary_category=product.primary_category).exclude(pk=product.pk)[:4], "public_documents": product.documents.filter(visibility="public"), "whatsapp_url": f"https://wa.me/{digits}?text={quote(message)}" if settings.show_whatsapp and digits else ""})


@require_POST
def add_quote_item(request):
    form = QuoteItemForm(request.POST)
    if form.is_valid():
        product = form.cleaned_data["product_id"]
        items = [item for item in request.session.get("quote_products", []) if item["id"] != product.pk]
        items.append({"id": product.pk, "quantity": form.cleaned_data["quantity"]})
        request.session["quote_products"] = items[:12]
        messages.success(request, f"{product.name} was added to your quote list.")
    else:
        messages.error(request, "We could not add that product to your quote list.")
    return redirect(safe_next(request, "catalogue:quote_list"))


def quote_list(request):
    items = request.session.get("quote_products", [])
    products = {product.pk: product for product in public_products().filter(pk__in=[item["id"] for item in items])}
    return render(request, "catalogue/quote_list.html", {"quote_items": [{"product": products[item["id"]], "quantity": item["quantity"]} for item in items if item["id"] in products]})


@require_POST
def toggle_compare(request):
    product = get_object_or_404(public_products(), pk=request.POST.get("product_id"))
    ids = request.session.get("compare_products", [])
    if product.pk in ids:
        ids.remove(product.pk)
    elif len(ids) < 4:
        ids.append(product.pk)
    else:
        messages.error(request, "You can compare up to four products.")
    request.session["compare_products"] = ids
    return redirect(safe_next(request, "catalogue:compare"))


def compare(request):
    ids = request.session.get("compare_products", [])
    products = list(public_products().filter(pk__in=ids))
    products.sort(key=lambda item: ids.index(item.pk))
    names = sorted({spec.name for product in products for spec in product.specifications.all()})
    rows = [(name, [next((f"{spec.value} {spec.unit}".strip() for spec in product.specifications.all() if spec.name == name), "—") for product in products]) for name in names]
    return render(request, "catalogue/compare.html", {"products": products, "rows": rows})


def search_suggestions(request):
    from django.urls import reverse
    from apps.cms.models import ContentPage
    query = request.GET.get("q", "").strip()[:100]
    if request.GET.get("discovery") == "1":
        categories = Category.objects.filter(is_active=True, is_published=True).values("name", "slug")[:100]
        recommended = Product.objects.filter(is_active=True, is_published=True, is_featured=True).order_by("display_order", "pk")[:4]
        return JsonResponse({"categories": list(categories), "recommended": [{"title": p.name, "url": p.get_absolute_url()} for p in recommended]})
    if len(query) < 2:
        return JsonResponse({"results": []})
    types = set(request.GET.getlist("type")) if "type" in request.GET else {"products"}
    results = []
    category = request.GET.get("category", "")[:80]
    if "products" in types:
        products = search_products(Product.objects.filter(is_active=True, is_published=True), query)
        if category:
            categories = list(Category.objects.filter(is_active=True, is_published=True))
            selected = next((item for item in categories if item.slug == category), None)
            slugs = descendants(selected, categories) if selected else {category}
            products = filter_categories(products, slugs)
        for item in products.order_by("name", "pk").values("name", "slug", "model_number")[:8]:
            results.append({"title": item["name"], "context": item["model_number"], "type": "Product", "url": reverse("catalogue:product_detail", args=[item["slug"]])})
    if "categories" in types:
        for item in Category.objects.filter(is_active=True, is_published=True, name__istartswith=query)[:4]:
            results.append({"title": item.name, "type": "Category", "url": reverse("catalogue:category_list", args=[item.slug])})
    for kind, label in [("services", "Service"), ("pages", "Page")]:
        if kind not in types:
            continue
        pages = ContentPage.objects.filter(is_published=True, title__istartswith=query)
        pages = pages.filter(kind="service") if kind == "services" else pages.exclude(kind="service")
        for item in pages[:4]:
            results.append({"title": item.title, "type": label, "url": item.get_absolute_url()})
    return JsonResponse({"results": results})


def verified_pairings():
    from django.utils import timezone
    return ProductCompatibility.objects.filter(
        is_active=True, is_verified=True, verified_on__lte=timezone.localdate(),
        product__is_active=True, product__is_published=True,
        companion__is_active=True, companion__is_published=True,
    ).exclude(requirements="").exclude(evidence_url="").select_related("companion")


@require_POST
def add_compatible_pair(request, pk):
    pairing = get_object_or_404(verified_pairings(), pk=pk)
    items = list(request.session.get("quote_products", []))
    existing = {item["id"] for item in items}
    additions = [{"id": product_id, "quantity": 1} for product_id in (pairing.product_id, pairing.companion_id) if product_id not in existing]
    if len(items) + len(additions) > 12:
        messages.error(request, "Your quote list is full. Request your current quote before adding this pair.")
    else:
        request.session["quote_products"] = items + additions
        messages.success(request, "Both products are in your quote list. Quantities, configuration and installation will be confirmed by the team.")
    return redirect("catalogue:quote_list")
