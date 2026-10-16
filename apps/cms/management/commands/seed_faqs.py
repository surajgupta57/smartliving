from django.core.management.base import BaseCommand
from django.db import transaction

from apps.cms.models import FAQ


FAQS = (
    (
        "Can I add smart devices to an existing home?",
        "Many smart devices can be added to an existing home. The right choice depends on your wiring, available space, network coverage and the equipment already installed. Share these details in a site survey or consultation request so suitability can be checked before you buy.",
    ),
    (
        "Will devices from different brands work together?",
        "Compatibility depends on the exact model, communication protocol, controller and required features. Check the compatibility information on each product page. Where a pairing has not been verified, request confirmation before placing an order.",
    ),
    (
        "Do I need a hub or gateway?",
        "Some devices connect directly to a compatible Wi-Fi network, while others require a suitable hub, gateway or controller. Check the requirements for the exact product and the functions you want to use when planning your system.",
    ),
    (
        "Will my smart home work without internet?",
        "This varies by device and system design. Some physical controls and local automations may continue to work, while remote access, cloud services and some voice controls may need internet. Confirm offline behaviour for the selected models before installation.",
    ),
    (
        "How can I request a quotation for my home or business?",
        "Use the consultation or site survey form to share your space, preferred features and existing equipment. You can also use the product finder to narrow down your requirements. Include the models and quantities you are considering so the proposed equipment and scope can be reviewed.",
    ),
    (
        "What should I check before buying or installing a device?",
        "Confirm the model, power supply, load rating, wiring requirements, network coverage and compatibility with your controller. Ask for the applicable warranty, installation scope and support terms in your quotation. Electrical installation should be carried out by a qualified professional.",
    ),
)


class Command(BaseCommand):
    help = "Add six published homepage FAQs, preserving existing FAQ entries."

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        created = skipped = 0
        for index, (question, answer) in enumerate(FAQS, start=1):
            if FAQ.objects.filter(question=question).exists():
                skipped += 1
                continue
            record = FAQ(question=question, answer=answer, display_order=index * 10, is_published=True)
            record.full_clean()
            if not options['dry_run']:
                record.save()
            created += 1
        action = 'Would create' if options['dry_run'] else 'Created'
        self.stdout.write(self.style.SUCCESS(f'{action} {created} FAQs; preserved {skipped} existing entries.'))
