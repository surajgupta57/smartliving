from django import forms
from django.contrib.auth import get_user_model
from django.forms import BaseInlineFormSet, inlineformset_factory
from .models import Enquiry, Proposal, ProposalLine
from .time_display import IST


class ISTDateTimeField(forms.DateTimeField):
    def to_python(self, value):
        from django.utils import timezone
        with timezone.override(IST):
            return super().to_python(value)


class ContactActivityForm(forms.Form):
    activity_type = forms.ChoiceField(label='Activity', choices=[('call', 'Phone call'), ('meeting', 'Meeting'), ('note', 'Internal note')])
    outcome = forms.CharField(label='Outcome / next step', max_length=160, required=False,
                              widget=forms.TextInput(attrs={'placeholder': 'For example: Connected; send a quotation'}))
    notes = forms.CharField(label='Notes', max_length=4000, widget=forms.Textarea(attrs={'rows': 4}))
    next_follow_up_at = ISTDateTimeField(label='Next follow-up (IST)', required=False,
        widget=forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={'type': 'datetime-local'}),
        help_text='Optional. Leave blank to keep the current follow-up.')

    def __init__(self, *args, lead, **kwargs):
        super().__init__(*args, **kwargs)
        self.lead = lead

    def clean_next_follow_up_at(self):
        from django.utils import timezone
        value = self.cleaned_data.get('next_follow_up_at')
        if value:
            if self.lead.status in ('won', 'lost'):
                raise forms.ValidationError('Reopen the enquiry before scheduling another follow-up.')
            if value <= timezone.now():
                raise forms.ValidationError('Choose a future follow-up time.')
        return value

class LeadWorkflowForm(forms.ModelForm):
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 3}), label='Activity note')
    class Meta:
        model = Enquiry
        fields = ('status', 'priority', 'assigned_to', 'follow_up_at')
        widgets = {'follow_up_at': forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={'type': 'datetime-local'})}
        help_texts = {'follow_up_at': 'India time (IST). This schedules the follow-up queue; no automatic message is sent.'}
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['assigned_to'].queryset = get_user_model().objects.filter(is_active=True, is_staff=True)

class ProposalForm(forms.ModelForm):
    class Meta:
        model = Proposal
        fields = ('title', 'valid_until', 'terms')
        widgets = {'valid_until': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}), 'terms': forms.Textarea(attrs={'rows': 3})}


class StaffEnquiryForm(forms.ModelForm):
    class Meta:
        model = Enquiry
        fields = ('name', 'phone', 'email', 'enquiry_type', 'property_type', 'project_stage', 'budget_range', 'source', 'message')
        widgets = {'message': forms.Textarea(attrs={'rows': 4})}

    def clean_phone(self):
        phone = self.cleaned_data['phone'].strip()
        if not 8 <= len(''.join(char for char in phone if char.isdigit())) <= 15:
            raise forms.ValidationError('Enter a valid contact number.')
        return phone

class ProposalLineForm(forms.ModelForm):
    class Meta:
        model = ProposalLine
        fields = ('description', 'quantity', 'unit_price', 'tax_rate')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['aria-label'] = field.label


class ProposalLineFormSet(BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for form in self.forms:
            # Any new row may be left blank; validate_min still requires one
            # completed line somewhere in the submitted formset.
            if not form.instance.pk:
                form.empty_permitted = True


ProposalLines = inlineformset_factory(Proposal, ProposalLine, form=ProposalLineForm, formset=ProposalLineFormSet, fields=('description', 'quantity', 'unit_price', 'tax_rate'), extra=4, min_num=1, validate_min=True, max_num=50, validate_max=True, absolute_max=50)


class SurveyWorkflowForm(forms.ModelForm):
    status = forms.ChoiceField(choices=[("requested", "Requested"), ("scheduled", "Scheduled"), ("completed", "Completed"), ("cancelled", "Cancelled")])

    class Meta:
        from .models import Consultation
        model = Consultation
        fields = ("status", "scheduled_at", "notes")
        widgets = {"scheduled_at": forms.DateTimeInput(format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}), "notes": forms.Textarea(attrs={"rows": 4})}
        help_texts = {"scheduled_at": "Confirmed appointment time in IST. Confirm with the customer first."}

    def clean(self):
        data = super().clean()
        from django.utils import timezone
        if data.get("status") == "scheduled":
            if not data.get("scheduled_at"):
                self.add_error("scheduled_at", "Set a confirmed appointment time.")
            elif data["scheduled_at"] <= timezone.now() and not (self.instance.status == 'scheduled' and self.instance.scheduled_at and data["scheduled_at"].replace(second=0, microsecond=0) == self.instance.scheduled_at.replace(second=0, microsecond=0)):
                self.add_error("scheduled_at", "Choose a future appointment time.")
        return data
