"""Isolated MySQL catalogue benchmark. Prompts for local admin credentials; never uses the business DB for fixtures."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import getpass
import json
import os
from pathlib import Path
import statistics
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sqlite', action='store_true', help='Development-only SQLite benchmark when MySQL is unavailable')
    parser.add_argument('--products', type=int, default=100000)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--requests', type=int, default=40)
    parser.add_argument('--report', default='var/catalogue-benchmark.json')
    args = parser.parse_args()
    if not 1000 <= args.products <= 200000 or not 1 <= args.workers <= 8 or not 10 <= args.requests <= 200:
        parser.error('Use 1000-200000 products, 1-8 workers and 10-200 requests.')
    if args.sqlite:
        os.environ['DJANGO_DB_ENGINE'] = 'sqlite'
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    import django
    django.setup()
    from django.conf import settings
    from django.db import connections, close_old_connections
    from django.test import Client, override_settings
    from django.test.runner import DiscoverRunner
    from django.test.utils import CaptureQueriesContext
    db = settings.DATABASES['default']
    if args.sqlite:
        db['TEST']['NAME'] = str(ROOT / 'var' / ('benchmark-' + uuid.uuid4().hex + '.sqlite3'))
    else:
        if connections['default'].vendor != 'mysql':
            raise SystemExit('Configure MySQL before benchmarking, or use --sqlite for development measurements.')
        admin = input('Local MySQL administrator user [root]: ').strip() or 'root'
        password = getpass.getpass('Local MySQL administrator password (hidden): ')
        db['USER'], db['PASSWORD'] = admin, password
        db['TEST']['NAME'] = 'test_smartliving_perf_' + uuid.uuid4().hex[:16]
    connections.close_all()
    connections['default'].settings_dict.update(db)
    if args.sqlite:
        if Path(db['TEST']['NAME']).exists():
            raise SystemExit('Temporary test path already exists; refusing to reuse it.')
    else:
        with connections['default'].cursor() as cursor:
            cursor.execute('SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME=%s', [db['TEST']['NAME']])
            if cursor.fetchone():
                raise SystemExit('Temporary database already exists; refusing to reuse it.')
    runner = DiscoverRunner(verbosity=0, interactive=False)
    old_config = runner.setup_databases()
    try:
        from apps.catalogue.models import Brand, Category, Product, ProductSearchToken, ProductImage
        from apps.catalogue.search import tokens, search_products
        from apps.core.models import SiteSettings
        SiteSettings.load()
        brands = [Brand.objects.create(name=f'Benchmark Brand {i}', slug=f'benchmark-brand-{i}', is_published=True) for i in range(10)]
        categories = [Category.objects.create(name=f'Benchmark Category {i}', slug=f'benchmark-category-{i}', is_published=True) for i in range(12)]
        settings.DEBUG = False
        started = time.perf_counter()
        for offset in range(0,args.products,1000):
            products = []
            for i in range(offset,min(offset+1000,args.products)):
                kind = ['Camera','Camera','Camera','Switch','Network'][i % 5]
                products.append(Product(name=f'{kind} System {i:06d}', slug=f'benchmark-product-{i}', sku=f'BENCH-{i:06d}', model_number=f'SL-{i:06d}', brand=brands[i%10], primary_category=categories[i%12], short_description='Synthetic benchmark product', is_active=True, is_published=True, is_featured=i%17==0, stock_status='in_stock' if i%3==0 else 'quote', price=i%50000))
            Product.objects.bulk_create(products, batch_size=1000)
            # MySQL does not return generated IDs from bulk_create.
            products = list(Product.objects.filter(slug__in=[p.slug for p in products]).select_related("brand"))
            rows = []
            for product in products:
                for token in tokens(' '.join([product.name,product.model_number,product.sku,product.brand.name])):
                    rows.append(ProductSearchToken(product=product,token=token))
            ProductSearchToken.objects.bulk_create(rows,batch_size=3000)
            ProductImage.objects.bulk_create([ProductImage(product=p,image='benchmark/placeholder.webp',is_primary=True) for p in products],batch_size=1000)
            if (offset + 1000) % 20000 == 0:
                print(f'Seeded {min(offset+1000,args.products)} products…',flush=True)
        seed_seconds = time.perf_counter()-started
        print(f'Seeded {args.products} synthetic products in isolated database in {seed_seconds:.1f}s',flush=True)
        workloads = {
            'suggestions_broad': ('/search/suggestions/', {'q':'camera'}, {}),
            'suggestions_model': ('/search/suggestions/', {'q':'SL-09999'}, {}),
            'suggestions_multiword': ('/search/suggestions/', {'q':'camera system'}, {}),
            'catalogue': ('/products/', {}, {'HTTP_X_CATALOGUE_LIVE':'1'}),
            'category_brand': ('/products/', {'category':'benchmark-category-1','brand':'benchmark-brand-1'}, {'HTTP_X_CATALOGUE_LIVE':'1'}),
            'search_results': ('/products/', {'q':'camera'}, {'HTTP_X_CATALOGUE_LIVE':'1'}),
            'deep_page': ('/products/', {'page':'2000'}, {'HTTP_X_CATALOGUE_LIVE':'1'}),
            'price_sort': ('/products/', {'sort':'price_low'}, {'HTTP_X_CATALOGUE_LIVE':'1'}),
        }
        results = {}
        with override_settings(DEBUG=False, ALLOWED_HOSTS=['localhost']):
            client=Client(HTTP_HOST='localhost')
            for name,(path,params,headers) in workloads.items():
                samples=[]
                for _ in range(5):
                    with CaptureQueriesContext(connections['default']) as queries:
                        started=time.perf_counter(); response=client.get(path,params,**headers); samples.append((time.perf_counter()-started)*1000)
                    assert response.status_code==200,(name,response.status_code)
                results[name]={'median_ms':round(statistics.median(samples),2),'max_ms':round(max(samples),2),'queries':len(queries)}
            def request_one(index):
                close_old_connections()
                try:
                    name=list(workloads)[index%len(workloads)]
                    path,params,headers=workloads[name]
                    started=time.perf_counter(); response=Client(HTTP_HOST='localhost').get(path,params,**headers)
                    assert response.status_code==200,(name,response.status_code)
                    return (time.perf_counter()-started)*1000
                finally:
                    connections.close_all()
            started=time.perf_counter()
            with ThreadPoolExecutor(max_workers=args.workers) as executor:
                concurrent=list(executor.map(request_one,range(args.requests)))
            elapsed=time.perf_counter()-started
        ordered=sorted(concurrent)
        report={'products':args.products,'search_tokens':ProductSearchToken.objects.count(),'database_vendor':connections['default'].vendor,'seed_seconds':round(seed_seconds,2),'serial':results,'concurrent':{'workers':args.workers,'requests':args.requests,'median_ms':round(statistics.median(concurrent),2),'p95_ms':round(ordered[int((len(ordered)-1)*.95)],2),'requests_per_second':round(len(concurrent)/elapsed,2)},'suggestion_plan':search_products(Product.objects.filter(is_active=True,is_published=True),'camera').order_by('name','pk').values('name','slug','model_number')[:8].explain(),'limitations':'Synthetic local data, in-process Django requests, no network/browser/image delivery or shared-host CPU limits. Not a production SLA.'}
        report_path=ROOT/args.report
        report_path.parent.mkdir(exist_ok=True)
        report_path.write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report,indent=2),flush=True)
    finally:
        connections.close_all()
        runner.teardown_databases(old_config)


if __name__=='__main__':
    main()
