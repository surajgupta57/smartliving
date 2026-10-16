from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from apps.catalogue.models import Product
import uuid


class Enquiry(models.Model):
    transfer_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    TYPES = [("product", "Product information"), ("quote", "Quote request"), ("installation", "Installation project"), ("consultation", "Site consultation"), ("amc", "AMC / support"), ("general", "General enquiry")]
    STATUS = [("new", "New"), ("contacted", "Contacted"), ("consultation", "Consultation scheduled"), ("proposal", "Proposal sent"), ("won", "Won"), ("lost", "Lost")]
    name = models.CharField(max_length=120)
    phone = models.CharField(max_length=30)
    email = models.EmailField(blank=True)
    enquiry_type = models.CharField(max_length=20, choices=TYPES, default="general")
    property_type = models.CharField(max_length=80, blank=True)
    project_stage = models.CharField(max_length=80, blank=True)
    budget_range = models.CharField(max_length=80, blank=True)
    message = models.TextField(blank=True)
    source = models.CharField(max_length=80, default="website")
    status = models.CharField(max_length=20, choices=STATUS, default="new")
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_enquiries")
    consent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    priority = models.CharField(max_length=10, choices=[("normal", "Normal"), ("high", "High"), ("urgent", "Urgent")], default="normal")
    follow_up_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        ordering = ("-created_at",)
        permissions = [("export_enquiry", "Can export enquiries")]
    def __str__(self): return f"{self.name} — {self.get_enquiry_type_display()}"


class EnquiryItem(models.Model):
    enquiry = models.ForeignKey(Enquiry, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="enquiry_items")
    requested_quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    installation_required = models.BooleanField(default=False)
    customer_note = models.CharField(max_length=300, blank=True)
    class Meta: unique_together = (("enquiry", "product"),)
    def __str__(self): return f"{self.product} × {self.requested_quantity}"


class LeadActivity(models.Model):
    enquiry = models.ForeignKey(Enquiry, on_delete=models.CASCADE, related_name="activities")
    activity_type = models.CharField(max_length=50, default="note")
    note = models.TextField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta: ordering = ("-created_at",)

    @property
    def activity_label(self):
        return {'call': 'Phone call', 'meeting': 'Meeting', 'note': 'Note',
                'workflow': 'Follow-up / workflow', 'proposal': 'Quotation',
                'survey': 'Site survey', 'survey_request': 'Survey request',
                'created': 'Enquiry created'}.get(self.activity_type, 'Activity')

    @property
    def display_note(self):
        # Format the old system-generated timestamp without changing audit data
        # or interpreting dates in the customer's/staff member's free-text note.
        if self.activity_type != "workflow" or not self.note.startswith("Workflow updated:"):
            return self.note
        import re
        from datetime import datetime
        from .time_display import format_ist

        first_line, separator, rest = self.note.partition("\n")
        pattern = r"(; follow-up )(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[+-]\d{2}:\d{2}|Z))(\.?)$"

        def replace(match):
            try:
                return match[1] + format_ist(datetime.fromisoformat(match[2])) + match[3]
            except ValueError:
                return match[0]

        return re.sub(pattern, replace, first_line) + separator + rest


class Consultation(models.Model):
    transfer_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    enquiry = models.ForeignKey(Enquiry, on_delete=models.CASCADE, related_name="consultations")
    scheduled_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=30, default="requested")
    meeting_type = models.CharField(max_length=50, default="site_visit")
    notes = models.TextField(blank=True)
    site_address = models.CharField(max_length=300, blank=True)
    preferred_at = models.DateTimeField(null=True, blank=True)
    service_type = models.CharField(max_length=80, blank=True)


class Proposal(models.Model):
    enquiry = models.ForeignKey(Enquiry, on_delete=models.PROTECT, related_name="proposals")
    title = models.CharField(max_length=180, default="System design and installation")
    status = models.CharField(max_length=20, choices=[("draft", "Draft"), ("sent", "Sent"), ("accepted", "Accepted"), ("declined", "Declined")], default="draft")
    valid_until = models.DateField()
    terms = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    customer_snapshot = models.JSONField(default=dict, editable=False)
    company_snapshot = models.JSONField(default=dict, editable=False)

    def save(self, *args, **kwargs):
        if not self.pk:
            from apps.core.models import SiteSettings
            company = SiteSettings.load()
            self.customer_snapshot = {key: getattr(self.enquiry, key) for key in ('name', 'phone', 'email')}
            self.company_snapshot = {key: getattr(company, key) for key in ('company_name', 'address', 'phone', 'email')}
        super().save(*args, **kwargs)

    @property
    def reference(self):
        return f"SL-Q-{self.pk:06d}"

    @property
    def subtotal(self):
        return sum((line.subtotal for line in self.lines.all()), 0)

    @property
    def tax_total(self):
        return sum((line.tax for line in self.lines.all()), 0)

    @property
    def total(self):
        return self.subtotal + self.tax_total


class ProposalLine(models.Model):
    proposal = models.ForeignKey(Proposal, on_delete=models.CASCADE, related_name="lines")
    description = models.CharField(max_length=240)
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])

    @property
    def subtotal(self):
        return self.quantity * self.unit_price

    @property
    def tax(self):
        from decimal import Decimal, ROUND_HALF_UP
        return (self.subtotal * self.tax_rate / Decimal(100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
