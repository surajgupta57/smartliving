import hashlib, io, json, tempfile
from pathlib import Path
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from PIL import Image
from .models import Brand, Category, Product, ProductImage, ProductSpecification

class PortableManufacturerSeedTests(TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root=Path(self.directory.name)
        self.bundle=self.root/'bundle';(self.bundle/'assets').mkdir(parents=True)
        self.media=self.root/'media'
        self.override=override_settings(MEDIA_ROOT=self.media)
        self.override.enable();self.addCleanup(self.override.disable)
        images=[]
        for color in ['white','blue']:
            output=io.BytesIO();Image.new('RGB',(200,200),color).save(output,'WEBP')
            data=output.getvalue();sha=hashlib.sha256(data).hexdigest()
            asset=self.bundle/'assets'/(sha+'.webp');asset.write_bytes(data)
            images.append({'path':'assets/'+asset.name,'sha256':sha,'source_url':'https://example.com/image.webp'})
        self.record={'key':'test:controller','sku':'TEST-CONTROLLER','brand':'Test Manufacturer','name':'Source controller','model_number':'CTRL-1','category':'Smart Home Automation','source_url':'https://example.com/products/controller','source_checked_at':'2026-10-14T10:00:00Z','short_description':'A source-backed controller.','full_description':'Source-backed device overview.','images':images,'documents':[],'features':[{'title':'Local control','description':'Local operation'}],'specifications':[{'name':f'Spec {i}','value':'Long specification '+('x'*250),'group':'Hardware'} for i in range(4)]}
        self.path=self.bundle/'manifest.json'
        self.write_manifest()

    def write_manifest(self):
        self.path.write_text(json.dumps({'schema_version':1,'product_count':1,'products':[self.record]}),encoding='utf-8')

    def seed(self, **kwargs):
        call_command('seed_manufacturer_catalogue',manifest=str(self.path),expected_count=1,stdout=io.StringIO(),**kwargs)

    def test_dry_run_does_not_modify_database_or_media(self):
        category_count = Category.objects.count()
        self.seed(dry_run=True)
        self.assertEqual(Product.objects.count(),0)
        self.assertEqual(Brand.objects.count(),0)
        self.assertEqual(Category.objects.count(),category_count)
        self.assertFalse(self.media.exists())

    def test_import_is_idempotent_and_preserves_staff_edits(self):
        self.seed(publish=True)
        product=Product.objects.get();product.name='Staff edited product';product.is_published=False;product.save()
        image=product.images.first();image.caption='Staff supplied caption';image.save()
        self.seed(publish=True)
        product.refresh_from_db();image.refresh_from_db()
        self.assertEqual(Product.objects.count(),1)
        self.assertEqual(product.name,'Staff edited product')
        self.assertFalse(product.is_published)
        self.assertEqual(image.caption,'Staff supplied caption')
        self.assertEqual(ProductImage.objects.count(),2)
        self.assertTrue(ProductSpecification.objects.filter(value__contains='x'*250).exists())
        self.assertIsNone(product.price)
        self.assertEqual(product.stock_status,'quote')

    def test_checksum_failure_rejects_all_writes(self):
        (self.bundle/self.record['images'][0]['path']).write_bytes(b'changed')
        with self.assertRaises(CommandError):self.seed()
        self.assertEqual(Product.objects.count(),0)
        self.assertFalse(self.media.exists())

    def test_path_traversal_rejected(self):
        self.record['images'][0]['path']='../outside.webp';self.write_manifest()
        with self.assertRaisesMessage(CommandError,'escapes bundle'):self.seed()
        self.assertEqual(Product.objects.count(),0)

    def test_duplicate_seed_identity_rejected(self):
        self.path.write_text(json.dumps({'schema_version':1,'product_count':2,'products':[self.record,self.record]}),encoding='utf-8')
        with self.assertRaisesMessage(CommandError,'Duplicate identity'):
            call_command('seed_manufacturer_catalogue',manifest=str(self.path),expected_count=2,stdout=io.StringIO())
        self.assertEqual(Product.objects.count(),0)

    def test_default_import_is_draft_and_published_detail_contains_quantity_input(self):
        self.seed()
        product=Product.objects.get()
        self.assertFalse(product.is_published)
        product.is_published=True;product.save()
        response=self.client.get(product.get_absolute_url())
        self.assertContains(response,'name="quantity"')
        self.assertContains(response,'Manufacturer reference')

class ManufacturerExtractionRegressionTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        import importlib.util
        from django.conf import settings
        source=settings.BASE_DIR/'scripts/build_manufacturer_seed.py'
        spec=importlib.util.spec_from_file_location('test_catalogue_collector',source)
        cls.collector=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.collector)

    def test_controller_is_not_misclassified_as_roller_shutter(self):
        c=self.collector
        self.assertEqual(c.classify('Zipato Zipabox2','https://www.zipato.com/product/zipabox2',[]),'Smart Home Automation')
        self.assertEqual(c.classify('Shelly i4 controller','https://www.shelly.com/products/shelly-i4',[]),'Smart Home Automation')
        self.assertEqual(c.classify('Motor controller','https://example.com/motor-controller',[]),'Smart Curtains and Blinds')

    def test_uppercase_memory_and_protocol_values_are_not_specification_headings(self):
        from bs4 import BeautifulSoup
        from unittest.mock import patch
        c=self.collector
        html='<div class="summary"><h1 class="product_title">ZipaTile2</h1></div><div id="tab-description"><h2>TECHNICAL SPECIFICATION</h2><p>SYSTEM</p><p>2GB RAM</p><p>8GB FLASH</p><p>Android 8.1 Oreo</p><p>NETWORK</p><p>Ethernet</p><p>DECT</p><h2>GALLERY</h2></div>'
        with patch.object(c,'soup_url',return_value=BeautifulSoup(html,'html.parser')):
            record=c.parse_zipato('https://www.zipato.com/product/zipatile2')
        rows={s['name']:s['value'] for s in record['specifications']}
        self.assertIn('2GB RAM',rows['System'])
        self.assertIn('8GB FLASH',rows['System'])
        self.assertIn('Android 8.1 Oreo',rows['System'])
        self.assertIn('DECT',rows['Network'])
        self.assertNotIn('8GB FLASH',rows)
