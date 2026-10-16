from django.core.management.base import BaseCommand
from apps.catalogue.models import Product
from apps.catalogue.search import index_products


class Command(BaseCommand):
    help = "Rebuild indexed product search after bulk updates/imports. Safe to rerun."

    def handle(self, **options):
        count = last_pk = 0
        upper_pk = Product.objects.order_by("-pk").values_list("pk", flat=True).first() or 0
        while True:
            # Keyset batches avoid MySQL buffering the entire product table.
            batch = list(Product.objects.select_related("brand").filter(pk__gt=last_pk, pk__lte=upper_pk).order_by("pk")[:500])
            if not batch:
                break
            index_products(batch)
            count += len(batch)
            last_pk = batch[-1].pk
        self.stdout.write(self.style.SUCCESS(f"Indexed {count} products."))
