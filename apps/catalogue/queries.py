from django.db.models import Prefetch

from .models import Product, ProductImage


def card_products():
    """Fetch only card fields and primary images; keep galleries on detail pages."""
    return Product.objects.filter(is_active=True, is_published=True).select_related("brand").only(
        "name", "slug", "sku", "model_number", "short_description", "featured_image",
        "price_display_mode", "price", "starting_price", "currency", "is_demo", "is_featured", "is_new", "brand__name",
    ).prefetch_related(Prefetch(
        "images", queryset=ProductImage.objects.filter(is_primary=True).only("product_id", "image", "is_primary"),
    ))
