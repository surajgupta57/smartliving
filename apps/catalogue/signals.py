from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Product, Brand
from .search import index_product


@receiver(post_save, sender=Product)
def update_product_search(sender, instance, using, raw=False, **kwargs):
    if not raw:
        index_product(instance, using)


@receiver(post_save, sender=Brand)
def update_brand_search(sender, instance, using, raw=False, **kwargs):
    if not raw:
        for product in instance.products.using(using).select_related("brand").iterator(chunk_size=500):
            index_product(product, using)
