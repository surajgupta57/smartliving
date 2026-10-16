import re
from django.db import transaction
from django.db.models import Subquery, OuterRef
from .models import ProductSearchToken


def tokens(value):
    words = re.findall(r"[^\W_]+(?:[-.][^\W_]+)*", value.casefold(), re.UNICODE)
    return list(dict.fromkeys(part[:100] for word in words for part in [word, *re.split(r"[-.]", word)] if part))


def index_products(products, using="default"):
    """Replace a bounded batch atomically; callers control batch memory usage."""
    products = list(products)
    if not products:
        return
    rows = []
    for product in products:
        text = " ".join([product.name, product.model_number, product.sku or "", product.brand.name if product.brand_id else ""])
        rows.extend(ProductSearchToken(product_id=product.pk, token=token) for token in tokens(text))
    with transaction.atomic(using=using):
        ProductSearchToken.objects.using(using).filter(product_id__in=[p.pk for p in products]).delete()
        ProductSearchToken.objects.using(using).bulk_create(rows, batch_size=1000)


def index_product(product, using="default"):
    index_products([product], using)


def search_products(queryset, query):
    terms = tokens(query)[:6]
    if not terms:
        return queryset.none()
    for position, term in enumerate(terms):
        # A bounded lexicographic prefix range uses the token B-tree index.
        upper = term[:-1] + chr(ord(term[-1]) + 1)
        matches = ProductSearchToken.objects.filter(token__gte=term, token__lt=upper).values("product_id")
        if position == 0:
            queryset = queryset.filter(pk__in=Subquery(matches))
        else:
            # Correlate remaining terms to each candidate. LIMIT keeps MySQL
            # from materializing a whole common-word posting list per term.
            match = matches.filter(product_id=OuterRef("pk"))[:1]
            queryset = queryset.filter(pk=Subquery(match))
    return queryset
