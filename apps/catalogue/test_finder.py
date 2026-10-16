from django.test import TestCase
from django.urls import reverse
from .models import Category, Product
from apps.leads.models import Enquiry
from .models import ProductPlanningProfile, ProductCompatibility
from django.utils import timezone
from datetime import timedelta
from django.core.exceptions import ValidationError


class ProductFinderTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Smart home", slug="smart-home-automation", is_published=True)
        self.product = Product.objects.create(name="Smart controller", primary_category=self.category, is_published=True)
        Product.objects.create(name="Private controller", primary_category=self.category, is_published=False)
        Product.objects.create(name="Retired controller", primary_category=self.category, is_published=True, stock_status="discontinued")
        self.data = {"property_type": "Home", "goal": "smart_home", "rooms": "4", "coverage": "indoor", "budget_range": "INR 25,000-50,000"}

    def test_published_family_products_are_bounded_and_private_products_hidden(self):
        response = self.client.get(reverse("catalogue:product_finder"), self.data)
        self.assertContains(response, "Smart controller")
        self.assertNotContains(response, "Private controller")
        self.assertNotContains(response, "Retired controller")
        self.assertLessEqual(len(response.context["finder_products"]), 8)
        self.assertNotIn("project_requirements", self.client.session)

    def test_invalid_choices_and_room_counts_do_not_handoff(self):
        for changes in [{"goal": "unknown"}, {"rooms": "-2"}, {"property_type": ""}]:
            data = {**self.data, **changes, "action": "quote"}
            response = self.client.post(reverse("catalogue:product_finder"), data)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["form"].errors)
            self.assertNotIn("project_requirements", self.client.session)

    def test_quote_handoff_preserves_shortlist_and_prefills_editable_requirements(self):
        session = self.client.session
        session["quote_products"] = [{"id": self.product.pk, "quantity": 2}]
        session.save()
        response = self.client.post(reverse("catalogue:product_finder"), {**self.data, "action": "quote"})
        self.assertRedirects(response, reverse("leads:request_quote"))
        self.assertEqual(self.client.session["quote_products"][0]["quantity"], 2)
        response = self.client.get(reverse("leads:request_quote"))
        form = response.context["form"]
        self.assertEqual(form.initial["property_type"], "Home")
        self.assertIn("Rooms / areas to cover: 4", form.initial["message"])
        payload = {"name": "Finder Customer", "phone": "9876543210", "enquiry_type": "quote", "message": form.initial["message"]}
        self.client.post(reverse("leads:request_quote"), payload)
        self.assertEqual(Enquiry.objects.count(), 0)
        self.assertIn("project_requirements", self.client.session)
        self.client.post(reverse("leads:request_quote"), {**payload, "consent": "on"})
        lead = Enquiry.objects.get()
        self.assertEqual(lead.source, "product_finder")
        self.assertEqual(lead.items.get().requested_quantity, 2)
        self.assertNotIn("project_requirements", self.client.session)

    def test_empty_family_still_allows_survey_request(self):
        data = {**self.data, "goal": "access"}
        response = self.client.get(reverse("catalogue:product_finder"), data)
        self.assertContains(response, "Let the team help you choose.")
        response = self.client.post(reverse("catalogue:product_finder"), {**data, "action": "survey"})
        self.assertRedirects(response, reverse("leads:site_survey"))
        response = self.client.get(reverse("leads:site_survey"))
        self.assertEqual(response.context["form"].initial["service_type"], "access")
        self.assertIn("Project requirements", response.context["form"].initial["message"])

    def test_non_cctv_requirements_do_not_inherit_camera_preferences(self):
        self.client.post(reverse("catalogue:product_finder"), {**self.data, "cameras": "8", "connection": "wired", "action": "quote"})
        self.assertNotIn("Cameras planned", self.client.session["project_requirements"]["summary"])


class FinderPlanningTests(TestCase):
    def setUp(self):
        self.category, _ = Category.objects.get_or_create(slug="cctv-cameras", defaults={"name": "Cameras", "is_published": True})
        self.category.is_published = True
        self.category.save()
        self.product = Product.objects.create(name="Planning camera", primary_category=self.category, is_published=True)
        self.profile = ProductPlanningProfile.objects.create(product=self.product, role="camera", environment="indoor", camera_technology="ip", camera_max_poe_watts=10, evidence_url="https://example.com/datasheet", verified_on=timezone.localdate(), is_verified=True)
        self.data = {"property_type": "Home", "goal": "cctv", "coverage": "outdoor", "cameras": "4"}

    def results(self, **changes):
        return self.client.get(reverse("catalogue:product_finder"), {**self.data, **changes})

    def test_verified_conflicts_excluded_unknowns_retained_and_stale_flags_ignored(self):
        unknown = Product.objects.create(name="Unknown camera", primary_category=self.category, is_published=True)
        result = self.results()
        self.assertNotIn(self.product, result.context["finder_products"])
        self.assertIn(unknown, result.context["finder_products"])
        self.profile.is_verified = False
        self.profile.save()
        self.assertIn(self.product, self.results().context["finder_products"])
        self.profile.is_verified = True
        self.profile.verified_on = timezone.localdate() + timedelta(days=1)
        self.profile.save()
        self.assertIn(self.product, self.results().context["finder_products"])

    def test_verified_matches_are_selected_before_result_limit(self):
        for number in range(12):
            Product.objects.create(name=f"A unknown {number}", primary_category=self.category, is_published=True)
        result = self.results(coverage="indoor")
        self.assertEqual(result.context["finder_products"][0].pk, self.product.pk)
        self.assertLessEqual(len(result.context["finder_products"]), 8)
        self.assertContains(result, "Verified use: Indoor only")

    def test_technology_conflict_is_excluded_even_with_matching_family(self):
        self.category, _ = Category.objects.get_or_create(slug="cctv-ip-cameras", defaults={"name": "IP cameras", "is_published": True})
        self.category.is_published = True
        self.category.save()
        self.product.primary_category = self.category
        self.product.save()
        self.profile.camera_technology = "analog"
        self.profile.save()
        self.assertNotIn(self.product, self.results(coverage="indoor", connection="wired").context["finder_products"])

    def test_camera_count_budget_is_product_only_and_unknown_prices_are_retained(self):
        self.product.price_display_mode = "exact"
        self.product.price = 7000
        self.product.save()
        self.assertNotIn(self.product, self.results(coverage="indoor", budget_range="Under INR 25,000").context["finder_products"])
        self.assertIn(self.product, self.results(coverage="indoor", cameras="3", budget_range="Under INR 25,000").context["finder_products"])
        self.product.price_display_mode = "starting"
        self.product.starting_price = 7000
        self.product.save()
        self.assertIn(self.product, self.results(coverage="indoor", budget_range="Under INR 25,000").context["finder_products"])

    def test_recorder_capacity_and_poe_capacity_exclude_insufficient_companions(self):
        companion = Product.objects.create(name="Small recorder", primary_category=self.category, is_published=True)
        capacity = ProductPlanningProfile.objects.create(product=companion, role="recorder", recorder_channels=2, evidence_url="https://example.com/recorder", verified_on=timezone.localdate(), is_verified=True)
        link = ProductCompatibility.objects.create(product=self.product, companion=companion, role="recorder", requirements="Supported configuration", evidence_url="https://example.com/pair", verified_on=timezone.localdate(), is_verified=True)
        result = self.results(coverage="indoor")
        self.assertEqual(result.context["finder_products"][0].finder_companions, [])
        capacity.recorder_channels = 8
        capacity.save()
        self.assertEqual(len(self.results(coverage="indoor").context["finder_products"][0].finder_companions), 1)
        link.role = "power"
        link.save()
        capacity.role = "poe"
        capacity.recorder_channels = None
        capacity.poe_ports = 8
        capacity.poe_budget_watts = 30
        capacity.save()
        self.assertEqual(self.results(coverage="indoor").context["finder_products"][0].finder_companions, [])
        capacity.poe_budget_watts = 60
        capacity.save()
        self.assertEqual(len(self.results(coverage="indoor").context["finder_products"][0].finder_companions), 1)
        companion.is_published = False
        companion.save()
        self.assertEqual(self.results(coverage="indoor").context["finder_products"][0].finder_companions, [])

    def test_planning_profile_requires_date_and_correct_role_fields(self):
        self.profile.verified_on = None
        with self.assertRaises(ValidationError):
            self.profile.full_clean()
        self.profile.verified_on = timezone.localdate()
        self.profile.recorder_channels = 8
        with self.assertRaises(ValidationError):
            self.profile.full_clean()

    def test_combined_pair_budget_and_discontinued_companion(self):
        self.product.price_display_mode = "exact"
        self.product.price = 5000
        self.product.save()
        companion = Product.objects.create(name="Expensive hub", primary_category=self.category, is_published=True, price_display_mode="exact", price=10000)
        ProductCompatibility.objects.create(product=self.product, companion=companion, role="controller", requirements="Example conditions", evidence_url="https://example.com/pair", verified_on=timezone.localdate(), is_verified=True)
        options = self.results(coverage="indoor", budget_range="Under INR 25,000").context["finder_products"][0]
        self.assertEqual(options.finder_companions, [])
        options = self.results(coverage="indoor", cameras="2", budget_range="Under INR 25,000").context["finder_products"][0]
        self.assertEqual(len(options.finder_companions), 1)
        companion.stock_status = "discontinued"
        companion.save()
        options = self.results(coverage="indoor", cameras="2").context["finder_products"][0]
        self.assertEqual(options.finder_companions, [])
