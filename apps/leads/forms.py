from datetime import timedelta
from django import forms
from django.utils import timezone
from .models import Enquiry


class EnquiryForm(forms.ModelForm):
    property_type = forms.ChoiceField(required=False, choices=[
        ("", "Choose property type"),
        ("Home", "Flat / apartment"),
        ("Independent house", "Independent house"),
        ("Villa", "Villa"),
        ("Office", "Office"),
        ("Retail", "Shop / showroom"),
        ("Warehouse", "Warehouse"),
        ("Factory", "Factory"),
        ("Facility", "Building / facility"),
        ("Other", "Other"),
    ])
    project_stage = forms.ChoiceField(required=False, choices=[
        ("", "Choose project stage"),
        ("Planning", "Planning"),
        ("Under construction", "Under construction"),
        ("Renovation", "Renovation"),
        ("Ready for installation", "Ready for installation"),
        ("Upgrading an existing system", "Upgrading an existing system"),
        ("Not sure", "Not sure yet"),
    ])
    consent = forms.BooleanField(label="I agree that Smart Living Technologies may contact me about this request.")
    class Meta:
        model = Enquiry
        fields = ("name", "phone", "email", "enquiry_type", "property_type", "project_stage", "budget_range", "message")
        widgets = {"message": forms.Textarea(attrs={"rows": 5}), "enquiry_type": forms.Select(), "name": forms.TextInput(attrs={"autocomplete": "name"}), "phone": forms.TextInput(attrs={"autocomplete": "tel", "inputmode": "tel", "type": "tel"}), "email": forms.EmailInput(attrs={"autocomplete": "email"})}

    def clean_phone(self):
        phone = self.cleaned_data["phone"].strip()
        digits = "".join(char for char in phone if char.isdigit())
        if len(digits) < 8 or len(digits) > 15:
            raise forms.ValidationError("Enter a valid contact number.")
        return phone

    def save(self, commit=True):
        enquiry = super().save(commit=False)
        enquiry.consent_at = timezone.now()
        if commit: enquiry.save()
        return enquiry


class SiteSurveyForm(EnquiryForm):
    site_address = forms.CharField(max_length=300, label="Site address / area and city", widget=forms.Textarea(attrs={"rows": 2, "autocomplete": "street-address"}))
    preferred_at = forms.DateTimeField(label="Preferred visit date and time", widget=forms.DateTimeInput(attrs={"type": "datetime-local"}), help_text="India time (IST). Our team will contact you to confirm availability.")
    service_type = forms.ChoiceField(label="What do you need help with?", choices=[("", "Choose a service"), ("cctv", "CCTV and surveillance"), ("smart_home", "Smart home automation"), ("networking", "Networking and Wi-Fi"), ("access", "Smart locks and access control"), ("amc", "Maintenance or upgrades"), ("multiple", "Multiple systems / help me choose")])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop("enquiry_type")
        self.fields["property_type"] = forms.ChoiceField(choices=[("", "Choose property type"), ("Home", "Home / apartment"), ("Office", "Office"), ("Retail", "Shop / showroom"), ("Facility", "Building / facility"), ("Other", "Other")])
        self.fields["message"].label = "Requirements and approximate property size"
        self.order_fields(["name", "phone", "email", "property_type", "site_address", "service_type", "preferred_at", "project_stage", "budget_range", "message", "consent"])

    def clean_preferred_at(self):
        value = self.cleaned_data["preferred_at"]
        if value <= timezone.now():
            raise forms.ValidationError("Choose a future date and time.")
        if value > timezone.now() + timedelta(days=180):
            raise forms.ValidationError("Choose a date within the next six months.")
        return value
