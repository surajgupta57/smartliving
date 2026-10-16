from django.core.exceptions import ValidationError
from django.db.models import Q
from import_export import fields, widgets
from apps.core.data_transfer import BusinessResource,MediaPathWidget
from .models import Brand,Category,Product,ProductImage,ProductSpecification,ProductFeature,ProductDocument

class CategoryListWidget(widgets.ManyToManyWidget):
    def __init__(self):super().__init__(Category,field='slug',separator='|')
    def clean(self,value,row=None,**kwargs):
        expected={part.strip() for part in str(value or '').split('|') if part.strip()}
        found=set(Category.objects.filter(slug__in=expected).values_list('slug',flat=True))
        if expected-found:raise ValidationError('Import additional categories first: '+', '.join(sorted(expected-found)))
        return Category.objects.filter(slug__in=expected)

class ProductReferenceWidget(widgets.ForeignKeyWidget):
    def __init__(self):super().__init__(Product,'sku')
    def clean(self,value,row=None,**kwargs):
        if not value:return None
        kind,sep,key=str(value).partition(':')
        if not sep or kind not in ['sku','slug']:raise ValidationError('Product reference must be sku:VALUE or slug:VALUE.')
        try:return Product.objects.get(**{kind:key})
        except Product.DoesNotExist:raise ValidationError(f'Import the parent product first: {value}')
    def render(self,value,obj=None,**kwargs):
        return ('sku:'+value.sku if value.sku else 'slug:'+value.slug) if value else ''

class BrandResource(BusinessResource):
    logo=fields.Field(attribute='logo',widget=MediaPathWidget())
    class Meta(BusinessResource.Meta):model=Brand;import_id_fields=('slug',)

class CategoryResource(BusinessResource):
    parent=fields.Field(attribute='parent',widget=widgets.ForeignKeyWidget(Category,'slug'))
    image=fields.Field(attribute='image',widget=MediaPathWidget())
    class Meta(BusinessResource.Meta):model=Category;import_id_fields=('slug',)

class ProductResource(BusinessResource):
    brand=fields.Field(attribute='brand',widget=widgets.ForeignKeyWidget(Brand,'slug'))
    primary_category=fields.Field(attribute='primary_category',widget=widgets.ForeignKeyWidget(Category,'slug'))
    additional_categories=fields.Field(attribute='additional_categories',widget=CategoryListWidget())
    featured_image=fields.Field(attribute='featured_image',widget=MediaPathWidget())
    source_key=fields.Field(attribute='source_key',widget=widgets.CharWidget())
    def get_instance(self,instance_loader,row):
        match=Q(slug=row.get('slug',''))
        if row.get('sku'):match|=Q(sku=row['sku'])
        if row.get('source_key'):match|=Q(source_key=row['source_key'])
        found=list(Product.objects.filter(match)[:2])
        if len(found)>1:raise ValidationError('Conflicting product identifiers; resolve the source key/SKU/slug before importing.')
        return found[0] if found else None
    def before_import_row(self,row,**kwargs):
        if not row.get('source_key'):row['source_key']=None
        if not row.get('sku'):row['sku']=None
    class Meta(BusinessResource.Meta):
        model=Product;import_id_fields=('slug',)
        exclude=('id','created_at','updated_at','published_at')

class SpecificationResource(BusinessResource):
    product=fields.Field(attribute='product',widget=ProductReferenceWidget())
    class Meta(BusinessResource.Meta):model=ProductSpecification;import_id_fields=('product','group','name','sort_order')

class FeatureResource(BusinessResource):
    product=fields.Field(attribute='product',widget=ProductReferenceWidget())
    class Meta(BusinessResource.Meta):model=ProductFeature;import_id_fields=('product','title','sort_order')

class ImageResource(BusinessResource):
    product=fields.Field(attribute='product',widget=ProductReferenceWidget())
    image=fields.Field(attribute='image',widget=MediaPathWidget())
    class Meta(BusinessResource.Meta):model=ProductImage;import_id_fields=('product','image');exclude=('id','created_at')

class DocumentResource(BusinessResource):
    product=fields.Field(attribute='product',widget=ProductReferenceWidget())
    file=fields.Field(attribute='file',widget=MediaPathWidget())
    class Meta(BusinessResource.Meta):model=ProductDocument;import_id_fields=('product','file')
