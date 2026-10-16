"""Verify the completed delivery archive and catalogue counts."""
import os, sys, json, hashlib, zipfile
from pathlib import Path
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root)); os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from apps.catalogue.models import Product, ProductImage, ProductSpecification, ProductFeature, ProductDocument
from django.db.models import Count, Min
archive = root / 'smartliving-catalogue-500.zip'
sha = hashlib.file_digest(archive.open('rb'), 'sha256').hexdigest()
assert sha == archive.with_suffix('.sha256').read_text().split()[0], 'Archive checksum mismatch'
with zipfile.ZipFile(archive) as bundle:
    assert bundle.testzip() is None, 'Corrupt archive member'
    manifest = json.loads(bundle.read('catalogue_seed/manufacturers/manifest.json'))
    assert manifest['product_count'] == 500
    assert bundle.read('catalogue_seed/manufacturers/manifest.json') == (root / 'catalogue_seed/manufacturers/manifest.json').read_bytes()
    names = set(bundle.namelist())
    for product in manifest['products']:
        for asset in product['images'] + product['documents']:
            assert 'catalogue_seed/manufacturers/' + asset['path'] in names
    for source in ['apps/catalogue/admin.py', 'apps/core/data_transfer.py', 'apps/leads/resources.py', 'config/settings.py', 'ADMIN_DATA_TRANSFER.md']:
        assert bundle.read(source) == (root / source).read_bytes(), 'Outdated source: ' + source
products = Product.objects.filter(source_key__isnull=False)
print('Products:', products.count(), 'Published:', products.filter(is_published=True).count())
print('Images:', ProductImage.objects.filter(product__in=products).count(), 'Specifications:', ProductSpecification.objects.filter(product__in=products).count())
print('Features:', ProductFeature.objects.filter(product__in=products).count(), 'PDFs:', ProductDocument.objects.filter(product__in=products).count())
print('Minimum gallery:', products.annotate(n=Count('images')).aggregate(Min('n')))
print('Missing features:', products.filter(features__isnull=True).count())
print('Archive verified:', archive.name, 'SHA256:', sha)
