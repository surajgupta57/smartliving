from django.template.loader import render_to_string
from django.test import TestCase
from django.urls import reverse

from .models import Brand, Category, Product, ProductImage
from .queries import card_products
from .views import public_products


class ProductCardPerformanceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        category = Category.objects.create(name="Performance cameras", is_published=True)
        brand = Brand.objects.create(name="Camera brand", is_published=True)
        for index in range(6):
            product = Product.objects.create(
                name=f"Performance camera {index}", primary_category=category, brand=brand,
                short_description="Camera", is_published=True, is_featured=True,
                featured_image="products/fallback.jpg",
            )
            ProductImage.objects.create(product=product, image="products/primary.jpg", is_primary=True)
            ProductImage.objects.create(product=product, image="products/extra.jpg")
        Product.objects.create(name="Private camera", primary_category=category)

    def test_six_cards_render_in_two_queries_without_gallery_payload(self):
        with self.assertNumQueries(2):
            products = list(card_products())
            html = "".join(render_to_string("catalogue/_product_card.html", {"product": p}) for p in products)
            for product in products:
                self.assertEqual(len(product.images.all()), 1)
        self.assertEqual(len(products), 6)
        self.assertIn("Camera brand", html)
        self.assertNotIn("Private camera", html)

    def test_card_output_matches_full_product_query(self):
        optimized = card_products().first()
        original = public_products().get(pk=optimized.pk)
        self.assertEqual(
            render_to_string("catalogue/_product_card.html", {"product": optimized}),
            render_to_string("catalogue/_product_card.html", {"product": original}),
        )

    def test_featured_image_fallback_does_not_query_per_product(self):
        ProductImage.objects.filter(is_primary=True).delete()
        with self.assertNumQueries(2):
            for product in card_products():
                self.assertEqual(product.public_image.name, "products/fallback.jpg")

    def test_home_uses_bounded_card_queryset(self):
        response = self.client.get(reverse("cms:home"), HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["featured_products"]), 6)
        self.assertNotContains(response, "Private camera")
