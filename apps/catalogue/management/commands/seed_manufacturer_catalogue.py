"""Offline, checksum-validated, idempotent manufacturer catalogue importer."""
import hashlib
import json
from pathlib import Path
from django.conf import settings
from django.core.files import File
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import URLValidator
from django.db import transaction
from django.db.models import Q
from django.utils.dateparse import parse_datetime
from django.utils.text import slugify
from apps.catalogue.models import Brand, Category, Product, ProductImage, ProductFeature, ProductSpecification, ProductDocument

class Command(BaseCommand):
    help = 'Import the portable manufacturer seed. Existing products and staff media are preserved.'

    def add_arguments(self, parser):
        parser.add_argument('--manifest', default=str(settings.BASE_DIR / 'catalogue_seed/manufacturers/manifest.json'))
        parser.add_argument('--dry-run', action='store_true', help='Validate all records and media checksums without writing anything.')
        parser.add_argument('--publish', action='store_true', help='Publish new records. Otherwise create drafts.')
        parser.add_argument('--expected-count', type=int, default=500)
        parser.add_argument('--limit', type=int, help='Import only the first N validated records for an operator smoke test.')

    def validate(self, path, expected):
        try:
            manifest=json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError) as exc: raise CommandError(f'Cannot read manifest: {exc}') from exc
        if manifest.get('schema_version') != 1: raise CommandError('Unsupported seed schema.')
        products=manifest.get('products')
        if not isinstance(products,list) or len(products)!=manifest.get('product_count'):raise CommandError('Invalid manifest product count.')
        if len(products)!=expected:raise CommandError(f'Expected {expected} products, found {len(products)}. Change --expected-count deliberately for another bundle.')
        keys=set();skus=set();assets={};url_validator=URLValidator(schemes=['https'])
        for index,p in enumerate(products,1):
            try:
                for name in ['key','sku','brand','name','category','source_url','short_description','full_description']:
                    if not isinstance(p.get(name),str) or not p[name].strip():raise ValueError(f'Missing {name}')
                if p['key'] in keys or p['sku'] in skus:raise ValueError('Duplicate identity or SKU')
                keys.add(p['key']);skus.add(p['sku'])
                for name,maxlen in [('key',200),('sku',64),('name',180),('brand',100),('category',100),('model_number',100),('source_url',600),('short_description',280)]:
                    if len(p.get(name,''))>maxlen:raise ValueError(f'{name} exceeds {maxlen} characters')
                url_validator(p['source_url'])
                if not parse_datetime(p.get('source_checked_at','')):raise ValueError('Invalid source timestamp')
                if len(p.get('images',[]))<2 or len(p.get('specifications',[]))<4:raise ValueError('Need two gallery images and four specifications')
                if len({a['sha256'] for a in p['images']})!=len(p['images']):raise ValueError('Duplicate gallery image')
                for spec in p['specifications']:
                    if not isinstance(spec.get('name'),str) or not isinstance(spec.get('value'),str) or not spec['name'].strip() or not spec['value'].strip() or len(spec['name'])>100 or len(spec.get('group',''))>80:raise ValueError('Invalid specification row')
                for feature in p.get('features',[]):
                    if not feature.get('title') or len(feature['title'])>120:raise ValueError('Invalid feature title')
                for asset in p['images']+p.get('documents',[]):
                    relative=Path(asset['path'])
                    absolute=(path.parent/relative).resolve()
                    if relative.is_absolute() or not absolute.is_relative_to(path.parent.resolve()):raise ValueError('Media path escapes bundle')
                    if absolute.suffix.lower() not in ['.webp','.pdf']:raise ValueError('Unsupported asset type')
                    checksum=asset['sha256']
                    if len(checksum)!=64 or any(c not in '0123456789abcdef' for c in checksum):raise ValueError('Invalid asset checksum')
                    if absolute not in assets:
                        if not absolute.is_file() or hashlib.sha256(absolute.read_bytes()).hexdigest()!=checksum:raise ValueError(f'Missing or changed media file: {relative}')
                        assets[absolute]=checksum
                    elif assets[absolute]!=checksum:raise ValueError('Conflicting asset checksums')
            except Exception as exc:raise CommandError(f'Product {index} ({p.get("name","unknown")}): {exc}') from exc
        return products

    def handle(self, *args, **options):
        path=Path(options['manifest']).resolve()
        products=self.validate(path,options['expected_count'])
        if options['limit'] is not None:
            if options['limit']<1:raise CommandError('--limit must be positive')
            products=products[:options['limit']]
        existing=set(Product.objects.filter(Q(source_key__in=[p['key'] for p in products])|Q(sku__in=[p['sku'] for p in products])).values_list('source_key','sku'))
        def is_existing(p):
            if any(p['key']==key or p['sku']==sku for key,sku in existing):return True
            if Product.objects.filter(source_url=p['source_url']).exists():return True
            return bool(p.get('model_number') and Product.objects.filter(brand__name=p['brand'],model_number=p['model_number']).exists())
        pending=[p for p in products if not is_existing(p)]
        self.stdout.write(f'Validated {len(products)} products; {len(pending)} new; {len(products)-len(pending)} existing products preserved.')
        if options['dry_run']:
            self.stdout.write(self.style.SUCCESS('Dry run complete. No database or media changes.'));return
        def asset_name(asset):
            suffix=Path(asset['path']).suffix
            target=f'products/manufacturer_seed/{asset["sha256"]}{suffix}'
            if not default_storage.exists(target):
                with (path.parent/asset['path']).open('rb') as stream:
                    saved=default_storage.save(target,File(stream))
                    if saved!=target:raise CommandError(f'Storage collision for {target}')
            return target
        created=0
        for p in pending:
            with transaction.atomic():
                # A concurrent import can finish this record between validation and insertion.
                if Product.objects.filter(Q(source_key=p['key'])|Q(sku=p['sku'])).exists():continue
                brand,_=Brand.objects.get_or_create(name=p['brand'],defaults={'slug':slugify(p['brand']),'is_published':True})
                category,_=Category.objects.get_or_create(name=p['category'],defaults={'slug':slugify(p['category']),'is_published':True})
                slug=slugify(p['name'])[:170]+'-'+hashlib.sha256(p['key'].encode()).hexdigest()[:8]
                product=Product.objects.create(name=p['name'],slug=slug,sku=p['sku'],model_number=p.get('model_number',''),brand=brand,primary_category=category,short_description=p['short_description'],full_description=p['full_description'],source_key=p['key'],source_url=p['source_url'],source_checked_at=parse_datetime(p['source_checked_at']),price_display_mode='quote',stock_status='quote',availability_label=p.get('availability_label','Confirm availability'),compatibility_information=p.get('compatibility_information',''),warranty_information=p.get('warranty_information',''),installation_required=p.get('installation_required',False),is_active=True,is_published=options['publish'],is_featured=p.get('is_featured',False),is_demo=False,meta_description=p['short_description'][:160])
                for category_name in p.get('additional_categories',[]):
                    additional,_=Category.objects.get_or_create(name=category_name,defaults={'is_published':True})
                    product.additional_categories.add(additional)
                ProductSpecification.objects.bulk_create([ProductSpecification(product=product,name=s['name'],value=s['value'],group=s.get('group',''),sort_order=i,is_verified=True) for i,s in enumerate(p['specifications'])])
                ProductFeature.objects.bulk_create([ProductFeature(product=product,title=f['title'],description=f.get('description',''),sort_order=i) for i,f in enumerate(p.get('features',[]))])
                for i,image in enumerate(p['images']):
                    ProductImage.objects.create(product=product,image=asset_name(image),alt_text=f'{p["name"]} — manufacturer gallery view {i+1}'[:180],caption='Manufacturer product image',image_type='main' if i==0 else 'detail',is_primary=i==0,sort_order=i)
                for i,doc in enumerate(p.get('documents',[])):
                    ProductDocument.objects.create(product=product,title=doc['title'][:160],file=asset_name(doc),visibility='public',sort_order=i)
                created+=1
            if created%25==0:self.stdout.write(f'Imported {created}/{len(pending)} products')
        from apps.catalogue.taxonomy import arrange_cctv_categories
        arrange_cctv_categories(Category)
        self.stdout.write(self.style.SUCCESS(f'Complete: {created} created; existing content preserved. New products are {"published" if options["publish"] else "drafts"}.'))
