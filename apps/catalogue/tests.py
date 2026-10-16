from django.test import TestCase
from django.urls import reverse
from .models import Category, Product, ProductSpecification


class CatalogueWorkflowTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="CCTV IP Cameras", is_published=True)
        self.product = Product.objects.create(name="Illustrative 4MP IP Camera", sku="DEMO-CAM-01", primary_category=self.category, short_description="A demonstration catalogue camera.", is_active=True, is_published=True, is_demo=True)
        ProductSpecification.objects.create(product=self.product, name="Resolution", value="4", unit="MP", is_verified=False)

    def test_published_product_is_browsable_and_unpublished_is_not(self):
        response = self.client.get(reverse("catalogue:product_detail", args=[self.product.slug]))
        self.assertContains(response, self.product.name)
        hidden = Product.objects.create(name="Private camera", sku="PRIVATE-1", primary_category=self.category, short_description="Hidden", is_published=False)
        self.assertEqual(self.client.get(reverse("catalogue:product_detail", args=[hidden.slug])).status_code, 404)

    def test_quote_list_and_product_enquiry_are_server_verified(self):
        response = self.client.post(reverse("catalogue:add_quote_item"), {"product_id": self.product.pk, "quantity": 2})
        self.assertRedirects(response, reverse("catalogue:quote_list"))
        self.assertEqual(self.client.session["quote_products"], [{"id": self.product.pk, "quantity": 2}])
        response = self.client.post(reverse("leads:product_enquiry", args=[self.product.slug]), {"name": "Asha", "phone": "9876543210", "email": "asha@example.com", "enquiry_type": "product", "message": "Need two cameras", "consent": "on"})
        self.assertRedirects(response, self.product.get_absolute_url())
        self.assertEqual(self.product.enquiry_items.get().enquiry.name, "Asha")

    def test_external_redirect_is_rejected(self):
        response = self.client.post(reverse('catalogue:add_quote_item'), {'product_id':self.product.pk, 'quantity':1, 'next':'https://example.com/trap'})
        self.assertRedirects(response, reverse('catalogue:quote_list'))

    def test_catalogue_pagination_preserves_filters_and_hides_private_products(self):
        for index in range(25):
            Product.objects.create(name=f'Published camera {index}', primary_category=self.category, short_description='Camera', is_published=True)
        Product.objects.create(name='Private camera', primary_category=self.category, short_description='Private', is_published=False)
        response = self.client.get(reverse('catalogue:product_list') + '?q=camera&page=2')
        self.assertEqual(response.context['page'].number, 2)
        self.assertEqual(response.context['page'].paginator.count, 26)
        self.assertEqual(len(response.context['products']), 2)
        self.assertNotContains(response, 'Private camera')
        self.assertContains(response, 'q=camera')


class LiveSearchTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Cameras", is_published=True)
        self.product = Product.objects.create(name="Network Bullet Camera", model_number="DS-2CD2043", primary_category=self.category, is_published=True)

    def test_prefix_multiword_and_model_search(self):
        for query in ["net bul", "DS-2CD", "2cd204"]:
            response = self.client.get(reverse("catalogue:search_suggestions"), {"q": query})
            self.assertEqual([item["title"] for item in response.json()["results"]], [self.product.name])

    def test_hidden_and_short_queries_are_excluded(self):
        self.product.is_published = False
        self.product.save()
        for query in ["network", "n", "%%"]:
            self.assertEqual(self.client.get(reverse("catalogue:search_suggestions"), {"q": query}).json()["results"], [])

    def test_updates_replace_old_terms(self):
        self.product.name = "Door Controller"
        self.product.save()
        self.assertEqual(self.client.get(reverse("catalogue:search_suggestions"), {"q": "network"}).json()["results"], [])
        self.assertEqual(len(self.client.get(reverse("catalogue:search_suggestions"), {"q": "door"}).json()["results"]), 1)

    def test_fragment_filters_and_page_size(self):
        response = self.client.get(reverse("catalogue:product_list"), {"q": "network", "per_page": "12"}, HTTP_X_CATALOGUE_LIVE="1")
        self.assertContains(response, 'Network Bullet Camera')
        self.assertIn("html", response.json())
        response = self.client.get(reverse("catalogue:product_list"), {"sort": "invalid"})
        self.assertEqual(response.context["page"].paginator.count, 0)

    def test_suggestions_are_bounded_and_do_not_fetch_images(self):
        from django.test.utils import CaptureQueriesContext
        from django.db import connection
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse("catalogue:search_suggestions"), {"q": "network"})
        self.assertEqual(len(response.json()["results"]), 1)
        self.assertLessEqual(len(queries), 1)
        self.assertNotIn("productimage", queries[0]["sql"])


class HeaderSearchPanelTests(TestCase):
    def test_search_scopes_and_public_discovery(self):
        from apps.cms.models import ContentPage
        category = Category.objects.create(name="Smart locks", is_published=True)
        Product.objects.create(name="Smart Lock", primary_category=category, is_published=True, is_featured=True)
        Product.objects.create(name="Private Lock", primary_category=category, is_published=False, is_featured=True)
        ContentPage.objects.create(title="Smart installation", kind="service", slug="smart-installation", is_published=True)
        ContentPage.objects.create(title="Smart planning", kind="solution", slug="smart-planning", is_published=True)
        ContentPage.objects.create(title="Smart private", kind="service", slug="smart-private", is_published=False)
        endpoint = reverse("catalogue:search_suggestions")
        data = self.client.get(endpoint, {"discovery": "1"}).json()
        self.assertEqual(len(data["recommended"]), 1)
        self.assertEqual(data["categories"][0]["name"], category.name)
        data = self.client.get(endpoint, {"q": "smart", "type": ["services", "pages", "categories"]}).json()
        self.assertEqual({item["type"] for item in data["results"]}, {"Service", "Page", "Category"})
        self.assertNotIn("Smart private", [item["title"] for item in data["results"]])
        response = self.client.get(reverse("catalogue:product_list"))
        self.assertContains(response, 'role="dialog"')
        self.assertContains(response, 'data-search-open')


class SearchRebuildTests(TestCase):
    def test_bulk_rebuild_replaces_stale_terms_and_preserves_public_visibility(self):
        from django.core.management import call_command
        from .models import ProductSearchToken
        category = Category.objects.create(name="Controllers", is_published=True)
        product = Product.objects.create(name="Old controller", primary_category=category, is_published=True)
        Product.objects.filter(pk=product.pk).update(name="Replacement gateway")
        hidden = Product.objects.create(name="Private gateway", primary_category=category, is_published=False)
        call_command("rebuild_product_search", verbosity=0)
        self.assertFalse(ProductSearchToken.objects.filter(product=product, token="old").exists())
        self.assertTrue(ProductSearchToken.objects.filter(product=product, token="replacement").exists())
        response = self.client.get(reverse("catalogue:search_suggestions"), {"q": "gateway"})
        self.assertEqual([item["title"] for item in response.json()["results"]], ["Replacement gateway"])
        count = ProductSearchToken.objects.count()
        call_command("rebuild_product_search", verbosity=0)
        self.assertEqual(ProductSearchToken.objects.count(), count)


class CategoryMembershipTests(TestCase):
    def test_multiple_category_memberships_do_not_duplicate_results(self):
        root = Category.objects.create(name="Systems", is_published=True)
        child = Category.objects.create(name="Cameras", parent=root, is_published=True)
        other = Category.objects.create(name="Accessories", parent=root, is_published=True)
        product = Product.objects.create(name="Camera kit", primary_category=child, is_published=True)
        product.additional_categories.add(root, other)
        response = self.client.get(reverse("catalogue:product_list"), {"category": root.slug})
        self.assertEqual(response.context["page"].paginator.count, 1)
        response = self.client.get(reverse("catalogue:search_suggestions"), {"q": "camera", "category": root.slug})
        self.assertEqual(len(response.json()["results"]), 1)


class MultiwordSearchTests(TestCase):
    def test_every_word_must_match_the_same_product(self):
        category = Category.objects.create(name="Systems", is_published=True)
        Product.objects.create(name="Network system", primary_category=category, is_published=True)
        Product.objects.create(name="Camera system", primary_category=category, is_published=True)
        endpoint = reverse("catalogue:search_suggestions")
        self.assertEqual(self.client.get(endpoint, {"q": "network camera"}).json()["results"], [])
        for query in ["net sys", "sys net", "network net"]:
            results = self.client.get(endpoint, {"q": query}).json()["results"]
            self.assertEqual([item["title"] for item in results], ["Network system"])
