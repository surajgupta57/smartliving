from import_export import fields, widgets
from apps.core.data_transfer import BusinessResource,MediaPathWidget,UUIDWidget
from .models import ContentPage,FAQ,HomeSection

class ContentPageResource(BusinessResource):
    hero_image=fields.Field(attribute='hero_image',widget=MediaPathWidget())
    card_image=fields.Field(attribute='card_image',widget=MediaPathWidget())
    class Meta(BusinessResource.Meta):model=ContentPage;import_id_fields=('kind','slug');exclude=('id','created_at','updated_at')

class HomeSectionResource(BusinessResource):
    transfer_id=fields.Field(attribute='transfer_id',widget=UUIDWidget())
    desktop_image=fields.Field(attribute='desktop_image',widget=MediaPathWidget())
    mobile_image=fields.Field(attribute='mobile_image',widget=MediaPathWidget())
    class Meta(BusinessResource.Meta):model=HomeSection;import_id_fields=('transfer_id',)

class FAQResource(BusinessResource):
    transfer_id=fields.Field(attribute='transfer_id',widget=UUIDWidget())
    class Meta(BusinessResource.Meta):model=FAQ;import_id_fields=('transfer_id',)
