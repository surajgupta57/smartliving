from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from import_export import fields,widgets
from apps.core.data_transfer import BusinessResource, PreciseDateTimeWidget, UUIDWidget
from apps.catalogue.resources import ProductReferenceWidget
from .models import Enquiry,EnquiryItem,Consultation,LeadActivity,Proposal,ProposalLine

class EnquiryResource(BusinessResource):
    transfer_id=fields.Field(attribute='transfer_id',widget=UUIDWidget())
    assigned_to=fields.Field(attribute='assigned_to',widget=widgets.ForeignKeyWidget(get_user_model(),'username'))
    consent_at=fields.Field(attribute='consent_at',widget=PreciseDateTimeWidget())
    created_at=fields.Field(attribute='created_at',widget=PreciseDateTimeWidget(),readonly=True)
    def before_import_row(self,row,**kwargs):
        phone=str(row.get('phone','')).strip()
        if phone.startswith("'+"):phone=phone[1:];row['phone']=phone
        if not 8<=len(''.join(c for c in phone if c.isdigit()))<=15:raise ValidationError('Enter a valid customer phone number.')
        username=row.get('assigned_to')
        if username and not get_user_model().objects.filter(username=username,is_staff=True,is_active=True).exists():raise ValidationError('Enquiry owners must be existing active staff users.')
    def after_init_instance(self,instance,new,row,**kwargs):
        instance._transfer_created_at=PreciseDateTimeWidget().clean(row.get('created_at')) if new and row.get('created_at') else None
    def after_save_instance(self,instance,row,**kwargs):
        if instance._transfer_created_at:
            Enquiry.objects.filter(pk=instance.pk).update(created_at=instance._transfer_created_at)
            instance.created_at=instance._transfer_created_at
        LeadActivity.objects.create(enquiry=instance,created_by=self.actor,activity_type='import',note='Enquiry imported through reviewed Admin data transfer.')
    class Meta(BusinessResource.Meta):model=Enquiry;import_id_fields=('transfer_id',);exclude=('id','updated_at')

class EnquiryItemResource(BusinessResource):
    enquiry=fields.Field(attribute='enquiry',widget=widgets.ForeignKeyWidget(Enquiry,'transfer_id'))
    product=fields.Field(attribute='product',widget=ProductReferenceWidget())
    class Meta(BusinessResource.Meta):model=EnquiryItem;import_id_fields=('enquiry','product')

class ConsultationResource(BusinessResource):
    transfer_id=fields.Field(attribute='transfer_id',widget=UUIDWidget())
    enquiry=fields.Field(attribute='enquiry',widget=widgets.ForeignKeyWidget(Enquiry,'transfer_id'))
    class Meta(BusinessResource.Meta):model=Consultation;import_id_fields=('transfer_id',)

class ActivityResource(BusinessResource):
    enquiry=fields.Field(attribute='enquiry',widget=widgets.ForeignKeyWidget(Enquiry,'transfer_id'))
    created_by=fields.Field(attribute='created_by',widget=widgets.ForeignKeyWidget(get_user_model(),'username'))
    class Meta(BusinessResource.Meta):model=LeadActivity

class ProposalResource(BusinessResource):
    enquiry=fields.Field(attribute='enquiry',widget=widgets.ForeignKeyWidget(Enquiry,'transfer_id'))
    created_by=fields.Field(attribute='created_by',widget=widgets.ForeignKeyWidget(get_user_model(),'username'))
    reference=fields.Field(attribute='reference',readonly=True)
    subtotal=fields.Field(attribute='subtotal',readonly=True)
    tax_total=fields.Field(attribute='tax_total',readonly=True)
    total=fields.Field(attribute='total',readonly=True)
    class Meta(BusinessResource.Meta):model=Proposal

class ProposalLineResource(BusinessResource):
    proposal=fields.Field(attribute='proposal',widget=widgets.ForeignKeyWidget(Proposal,'id'))
    quotation_reference=fields.Field(attribute='proposal__reference',readonly=True)
    subtotal=fields.Field(attribute='subtotal',readonly=True)
    tax=fields.Field(attribute='tax',readonly=True)
    class Meta(BusinessResource.Meta):model=ProposalLine
