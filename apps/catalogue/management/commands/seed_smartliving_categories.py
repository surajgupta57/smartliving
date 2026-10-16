from django.core.management.base import BaseCommand

from apps.catalogue.models import Category
from apps.catalogue.taxonomy import arrange_cctv_categories


CATEGORIES = [
    ("Smart Home Automation", "Automation"), ("Smart Switches and Lighting", "Lighting"),
    ("CCTV IP Cameras", "CCTV"), ("HD Analog CCTV Cameras", "CCTV"),
    ("Dome and Turret Cameras", "CCTV"), ("Bullet Cameras", "CCTV"),
    ("PTZ Cameras", "CCTV"), ("Wi-Fi and 4G Cameras", "CCTV"),
    ("NVR and DVR Recorders", "Recording"), ("CCTV Kits and Recording Systems", "CCTV"),
    ("CCTV Accessories", "Accessories"), ("Video Door Phones and Smart Doorbells", "Entry"),
    ("Smart Locks and Access Control", "Access"), ("Intrusion Alarms and Smart Sensors", "Security"),
    ("Smart Curtains and Blinds", "Automation"), ("Climate and Appliance Control", "Climate"),
    ("Home Theater and Audio", "Entertainment"), ("Networking and PoE Switches", "Network"),
    ("Wi-Fi Routers and Access Points", "Network"), ("Installation Accessories", "Accessories"),
    ("AMC and Maintenance Plans", "Support"),
]


class Command(BaseCommand):
    help = "Create the editable Smart Living catalogue categories without overwriting existing content."

    def handle(self, *args, **options):
        created = 0
        for order, (name, icon) in enumerate(CATEGORIES, start=1):
            _, was_created = Category.objects.get_or_create(
                name=name,
                defaults={"icon": icon, "display_order": order, "is_featured": order <= 6, "is_active": True, "is_published": True},
            )
            created += was_created
        arrange_cctv_categories(Category)
        self.stdout.write(self.style.SUCCESS(f"Smart Living categories ready; {created} created, {len(CATEGORIES) - created} already existed."))
