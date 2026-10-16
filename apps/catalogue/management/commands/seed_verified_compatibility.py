"""Small curated set checked against manufacturer documentation on 15 October 2026."""
from datetime import date
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from apps.catalogue.models import Product, ProductCompatibility


GATEWAY = "https://www.ezviz.com/product/A3-Home-Gateway/40264"
SOURCES = (
    "https://www.ezviz.com/product/T1C-PIR-Motion-Sensor/40328",
    "https://www.ezviz.com/product/T2C-Open-Close-Sensor/40419",
)
REQUIREMENTS = (
    "Manufacturer-documented pairing with the EZVIZ A3 Home Gateway using ZigBee 3.0. "
    "The sensor requires the EZVIZ Sensor Kit; the gateway is sold separately. "
    "Pair and manage through the EZVIZ App. This record covers sensor-to-gateway compatibility only. "
    "Camera linking requires the gateway and a supported wired EZVIZ camera with firmware 5.3.4 or later; "
    "confirm the exact camera with EZVIZ support. Regional variants, firmware and site coverage must "
    "be checked before supply. Documentation reviewed; no physical installation test was performed."
)


class Command(BaseCommand):
    help = "Add two manufacturer-documented EZVIZ sensor/A3 pairings without replacing staff records."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        products = {}
        for source in (GATEWAY, *SOURCES):
            matches = list(Product.objects.filter(source_url=source, is_active=True, is_published=True)[:2])
            if len(matches) != 1:
                raise CommandError(f"Expected one public product for {source}; no pairings written.")
            products[source] = matches[0]
        for source in SOURCES:
            product, companion = products[source], products[GATEWAY]
            if ProductCompatibility.objects.filter(product=product, companion=companion).exists():
                self.stdout.write(f"Preserved existing pairing: {product} / {companion}")
                continue
            pairing = ProductCompatibility(product=product, companion=companion, role="controller", requirements=REQUIREMENTS, evidence_url=source, verified_on=date(2026, 10, 15), is_verified=True)
            pairing.full_clean()
            if not options["dry_run"]:
                pairing.save()
            self.stdout.write(f"{'Would create' if options['dry_run'] else 'Created'}: {product} / {companion}")
