from django.test import TestCase
from .models import Category, Product
from .taxonomy import arrange_cctv_categories

class CCTVNavigationTests(TestCase):
    def setUp(self):
        self.ip = Category.objects.create(name='CCTV IP Cameras', slug='cctv-ip-cameras', is_published=True)
        self.wifi = Category.objects.create(name='Wi-Fi and 4G Cameras', slug='wi-fi-and-4g-cameras', is_published=True)
        self.dome = Category.objects.create(name='Dome and Turret Cameras', slug='dome-and-turret-cameras', is_published=True)
        self.recorder = Category.objects.create(name='NVR and DVR Recorders', slug='nvr-and-dvr-recorders', is_published=True)
        arrange_cctv_categories(Category)
        self.camera = Product.objects.create(name='Wireless dome camera', primary_category=self.wifi, short_description='Camera', is_published=True)
        self.camera.additional_categories.add(self.dome)
        self.nvr = Product.objects.create(name='Recorder', primary_category=self.recorder, short_description='Recorder', is_published=True)
        Product.objects.create(name='Hidden camera', primary_category=self.ip, short_description='Private', is_published=False)

    def browse(self, **kwargs):
        return self.client.get('/products/', kwargs)

    def test_dropdown_groups_cctv_and_parent_includes_children(self):
        response = self.browse(category='cctv-surveillance')
        self.assertEqual(response.context['page'].paginator.count, 2)
        options = {category.slug for category in response.context['categories']}
        self.assertIn('cctv-surveillance', options)
        self.assertNotIn('cctv-ip-cameras', options)
        self.assertNotIn('nvr-and-dvr-recorders', options)
        self.assertNotContains(response, 'Hidden camera')

    def test_independent_filters_intersect_without_duplicates(self):
        response = self.browse(category='cctv-surveillance', product_type='cctv-cameras', camera_shape=self.dome.slug, camera_connection=self.wifi.slug, camera_technology='ip')
        self.assertEqual(list(response.context['products']), [self.camera])
        self.assertEqual(self.browse(category='cctv-surveillance', product_type=self.recorder.slug).context['page'].paginator.count, 1)
        self.assertEqual(self.browse(category='cctv-surveillance', camera_technology='analog').context['page'].paginator.count, 0)

    def test_old_category_links_work_and_can_switch_category(self):
        response = self.client.get('/products/category/wi-fi-and-4g-cameras/')
        self.assertEqual(list(response.context['products']), [self.camera])
        response = self.client.get('/products/category/wi-fi-and-4g-cameras/', {'category': 'cctv-surveillance', 'product_type': self.recorder.slug})
        self.assertEqual(list(response.context['products']), [self.nvr])

    def test_grouping_is_idempotent_and_preserves_product_identity(self):
        old_pk, old_slug = self.camera.pk, self.camera.slug
        arrange_cctv_categories(Category)
        self.camera.refresh_from_db()
        self.assertEqual((self.camera.pk, self.camera.slug), (old_pk, old_slug))
        self.assertEqual(Category.objects.filter(slug='cctv-surveillance').count(), 1)
