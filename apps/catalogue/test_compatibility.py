from datetime import timedelta
from django.core.exceptions import ValidationError
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from .models import Category, Product, ProductCompatibility


class CompatibilityTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name="Equipment", slug="equipment")
        self.product = Product.objects.create(name="Camera", primary_category=category, is_published=True)
        self.companion = Product.objects.create(name="Recorder", primary_category=category, is_published=True)
        self.link = ProductCompatibility.objects.create(product=self.product, companion=self.companion, role="recorder", requirements="Test configuration only", evidence_url="https://example.com/test", verified_on=timezone.localdate(), is_verified=True)
        self.url = reverse("catalogue:add_compatible_pair", args=[self.link.pk])

    def test_public_evidence_and_safe_escaping(self):
        self.link.requirements = '<script>alert(1)</script>'
        self.link.save()
        response = self.client.get(self.product.get_absolute_url())
        self.assertContains(response, "Works with.")
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, '<script>alert(1)</script>')
        self.assertContains(response, self.url)

    def test_private_unverified_inactive_or_incomplete_pair_is_hidden_and_rejected(self):
        for field, value in [("is_verified", False), ("is_active", False), ("verified_on", None), ("verified_on", timezone.localdate() + timedelta(days=1)), ("requirements", ""), ("evidence_url", "")]:
            original = getattr(self.link, field)
            setattr(self.link, field, value)
            self.link.save()
            self.assertNotContains(self.client.get(self.product.get_absolute_url()), self.url)
            self.assertEqual(self.client.post(self.url).status_code, 404)
            setattr(self.link, field, original)
            self.link.save()
        self.companion.is_published = False
        self.companion.save()
        self.assertNotContains(self.client.get(self.product.get_absolute_url()), self.url)
        self.assertEqual(self.client.post(self.url).status_code, 404)

    def test_add_pair_preserves_quantities_and_is_idempotent(self):
        session = self.client.session
        session["quote_products"] = [{"id": self.product.pk, "quantity": 8}]
        session.save()
        for _ in range(2):
            self.assertRedirects(self.client.post(self.url), reverse("catalogue:quote_list"))
        self.assertEqual(self.client.session["quote_products"], [{"id": self.product.pk, "quantity": 8}, {"id": self.companion.pk, "quantity": 1}])

    def test_full_list_never_partially_adds_pair(self):
        session = self.client.session
        items = [{"id": 1000 + i, "quantity": 1} for i in range(11)]
        session["quote_products"] = items
        session.save()
        self.client.post(self.url)
        self.assertEqual(self.client.session["quote_products"], items)

    def test_post_and_csrf_required(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.assertEqual(Client(enforce_csrf_checks=True).post(self.url).status_code, 403)

    def test_staff_validation(self):
        self.link.companion = self.product
        with self.assertRaises(ValidationError):
            self.link.full_clean()

        self.link.companion = self.companion
        self.link.verified_on = None
        with self.assertRaises(ValidationError):
            self.link.full_clean()


class CompatibilitySeedTests(TestCase):
    def test_dry_run_preserves_staff_records_and_missing_product_is_atomic(self):
        from io import StringIO
        from django.core.management import call_command, CommandError
        from .management.commands.seed_verified_compatibility import GATEWAY, SOURCES
        category = Category.objects.create(name="Sensors", slug="sensors")
        for index, source in enumerate((GATEWAY, *SOURCES)):
            Product.objects.create(name=f"Device {index}", source_url=source, primary_category=category, is_published=True)
        call_command("seed_verified_compatibility", dry_run=True, stdout=StringIO())
        self.assertEqual(ProductCompatibility.objects.count(), 0)
        call_command("seed_verified_compatibility", stdout=StringIO())
        self.assertEqual(ProductCompatibility.objects.count(), 2)
        link = ProductCompatibility.objects.first()
        link.is_verified = False
        link.requirements = "Staff revision"
        link.save()
        call_command("seed_verified_compatibility", stdout=StringIO())
        link.refresh_from_db()
        self.assertFalse(link.is_verified)
        self.assertEqual(link.requirements, "Staff revision")
        ProductCompatibility.objects.all().delete()
        Product.objects.filter(source_url=SOURCES[-1]).update(is_published=False)
        with self.assertRaises(CommandError):
            call_command("seed_verified_compatibility", stdout=StringIO())
        self.assertEqual(ProductCompatibility.objects.count(), 0)
