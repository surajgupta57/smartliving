import io
import tempfile
import zipfile
from pathlib import Path
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.test import TestCase, override_settings, RequestFactory
from apps.catalogue.models import Brand, Category, Product, ProductSpecification, ProductImage
from apps.catalogue.resources import BrandResource, CategoryResource, ProductResource, SpecificationResource, ImageResource
from apps.cms.models import FAQ, HomeSection
from apps.cms.resources import FAQResource, HomeSectionResource
from apps.leads.models import Enquiry, LeadActivity
from apps.leads.resources import EnquiryResource
from .data_transfer import SiteSettingsResource
from .models import SiteSettings


class AdminTransferTests(TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        setting = override_settings(MEDIA_ROOT=self.directory.name)
        setting.enable(); self.addCleanup(setting.disable)
        self.owner = get_user_model().objects.create_superuser('transfer-owner', 'owner@example.com', 'test-only')
        self.brand = Brand.objects.create(name='Source brand', slug='source-brand')
        self.category = Category.objects.create(name='Controllers', slug='controllers')
        self.product = Product.objects.create(name='Controller', short_description='Local controller', slug='controller-' + 'x' * 110, sku='CTRL-1', brand=self.brand, primary_category=self.category)
        self.spec = ProductSpecification.objects.create(product=self.product, name='Memory', value='8 GB', group='')

    def assert_clean(self, result):
        self.assertFalse(result.has_errors(), repr(result.row_errors()) + repr(result.base_errors))
        self.assertFalse(result.has_validation_errors(), repr([(r.number, r.error) for r in result.invalid_rows]))

    def test_catalogue_transfer_uses_stable_references_across_databases(self):
        resources = [BrandResource(), CategoryResource(), ProductResource(), SpecificationResource()]
        data = [resource.export() for resource in resources]
        old_id = self.product.pk
        self.product.delete(); self.brand.delete(); self.category.delete()
        Brand.objects.create(name='Unrelated brand', slug='unrelated-brand')
        Category.objects.create(name='Unrelated category', slug='unrelated-category')
        for resource, dataset in zip(resources, data):
            self.assert_clean(resource.import_data(dataset, dry_run=False))
        restored = Product.objects.get(sku='CTRL-1')
        self.assertNotEqual(restored.pk, old_id)
        self.assertEqual(restored.brand.slug, 'source-brand')
        self.assertEqual(restored.specifications.get().value, '8 GB')
        for resource, dataset in zip(resources, data):
            self.assert_clean(resource.import_data(dataset, dry_run=False))
        self.assertEqual(Product.objects.count(), 1)
        self.assertEqual(ProductSpecification.objects.count(), 1)

    def test_missing_category_rolls_back_entire_import(self):
        resource = ProductResource(); data = resource.export()
        data.dict = [dict(data.dict[0], name='Changed', additional_categories='missing-category')]
        result = resource.import_data(data, dry_run=False)
        self.assertTrue(result.has_validation_errors() or result.has_errors())
        self.product.refresh_from_db(); self.assertEqual(self.product.name, 'Controller')

    def test_media_export_contains_gallery_and_rejects_missing_import_file(self):
        name = default_storage.save('products/test.webp', ContentFile(b'test-image'))
        ProductImage.objects.create(product=self.product, image=name)
        request = RequestFactory().get('/admin/'); request.user = self.owner
        response = admin.site._registry[Product].export_media(request, Product.objects.all())
        binary = b''.join(response.streaming_content); response.close()
        with zipfile.ZipFile(io.BytesIO(binary)) as archive:
            self.assertEqual(archive.read(name), b'test-image')
        resource = ImageResource(); data = resource.export()
        default_storage.delete(name)
        result = resource.import_data(data, dry_run=True)
        self.assertTrue(result.has_validation_errors() or result.has_errors())

    def test_cms_uuid_and_json_roundtrip(self):
        faq = FAQ.objects.create(question='Question?', answer='Answer')
        section = HomeSection.objects.create(section_type='hero_split', config={'items': ['first', 'second']})
        for model, resource, original in [(FAQ, FAQResource(), faq), (HomeSection, HomeSectionResource(), section)]:
            dataset = resource.export(); original_id = original.transfer_id
            original.delete()
            self.assert_clean(resource.import_data(dataset, dry_run=False))
            self.assert_clean(resource.import_data(dataset, dry_run=False))
            self.assertEqual(model.objects.count(), 1)
            self.assertEqual(model.objects.get().transfer_id, original_id)
        self.assertEqual(HomeSection.objects.get().config, {'items': ['first', 'second']})

    def test_enquiry_import_preserves_owner_timestamp_and_logs_actor(self):
        enquiry = Enquiry.objects.create(name='Customer', phone='+919876543210', assigned_to=self.owner)
        original_time = enquiry.created_at; original_uuid = enquiry.transfer_id
        resource = EnquiryResource(actor=self.owner); dataset = resource.export(); enquiry.delete()
        self.assert_clean(resource.import_data(dataset, dry_run=True))
        self.assertFalse(Enquiry.objects.exists()); self.assertFalse(LeadActivity.objects.exists())
        self.assert_clean(resource.import_data(dataset, dry_run=False))
        restored = Enquiry.objects.get()
        self.assertEqual(restored.transfer_id, original_uuid)
        self.assertEqual(restored.created_at, original_time)
        self.assertEqual(restored.assigned_to, self.owner)
        self.assertEqual(LeadActivity.objects.get().created_by, self.owner)
        self.assert_clean(resource.import_data(dataset, dry_run=False))
        self.assertEqual(LeadActivity.objects.count(), 1)

    def test_admin_buttons_and_bulk_permissions(self):
        self.client.force_login(self.owner)
        response = self.client.get('/admin/catalogue/product/')
        self.assertContains(response, '/admin/catalogue/product/import/')
        self.assertContains(response, '/admin/catalogue/product/export/')
        self.assertContains(response, 'value="export_media"')
        response = self.client.get('/admin/leads/proposal/')
        self.assertContains(response, '/admin/leads/proposal/export/')
        self.assertNotContains(response, '/admin/leads/proposal/import/')
        staff = get_user_model().objects.create_user('limited', is_staff=True)
        staff.user_permissions.add(*Permission.objects.filter(content_type__app_label='catalogue', codename__in=['view_product', 'add_product', 'change_product']))
        self.client.force_login(staff)
        self.assertEqual(self.client.get('/admin/catalogue/product/import/').status_code, 403)
        self.assertEqual(self.client.get('/admin/catalogue/product/export/').status_code, 403)

    def test_site_settings_is_singleton(self):
        settings = SiteSettings.load(); resource = SiteSettingsResource(); data = resource.export()
        self.assert_clean(resource.import_data(data, dry_run=False))
        self.assertEqual(SiteSettings.objects.count(), 1)
        data.append(data[0])
        self.assertTrue(resource.import_data(data, dry_run=False).has_errors())

    def test_import_page_previews_before_confirmation(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.client.force_login(self.owner)
        resource = ProductResource(); data = resource.export()
        data.dict = [dict(data.dict[0], name='Reviewed replacement')]
        upload = SimpleUploadedFile('products.json', data.json.encode(), content_type='application/json')
        response = self.client.post('/admin/catalogue/product/import/', {'format': '0', 'import_file': upload})
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.context['confirm_form'])
        self.assertFalse(response.context['result'].has_errors())
        self.assertFalse(response.context['result'].has_validation_errors())
        self.product.refresh_from_db(); self.assertEqual(self.product.name, 'Controller')
