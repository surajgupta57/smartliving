"""Shared admin transfer policies and lossless business resources."""
from pathlib import PurePosixPath
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.db.models import Q
from django.db import models
from django.http import FileResponse
import tempfile
import zipfile
from datetime import datetime
from uuid import UUID
from import_export import resources, fields, widgets
from import_export.admin import ImportExportModelAdmin, ExportMixin
from import_export.formats import base_formats
from .models import SiteSettings

FORMATS=[base_formats.JSON,base_formats.XLSX,base_formats.CSV]

class PreciseDateTimeWidget(widgets.DateTimeWidget):
    def render(self, value, obj=None, **kwargs):
        return value.isoformat() if value else ''
    def clean(self, value, row=None, **kwargs):
        if isinstance(value, datetime): return value
        if value:
            try: return datetime.fromisoformat(str(value).replace('Z', '+00:00'))
            except ValueError: pass
        return super().clean(value, row=row, **kwargs)

class UUIDWidget(widgets.CharWidget):
    def clean(self, value, row=None, **kwargs):
        return UUID(str(value)) if value else None
    def render(self, value, obj=None, **kwargs):
        return str(value) if value else ''

class MediaPathWidget(widgets.CharWidget):
    def clean(self,value,row=None,**kwargs):
        name=str(value or '').replace('\\','/').strip()
        if not name:return ''
        path=PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or ':' in name:raise ValidationError('Use a relative media path, not a URL or an absolute path.')
        if not default_storage.exists(name):raise ValidationError(f'Missing media: {name}. Copy the exported media files to the destination storage before importing.')
        return name
    def render(self,value,obj=None,**kwargs):return str(value or '')

class BusinessResource(resources.ModelResource):
    @classmethod
    def widget_from_django_field(cls, field, default=widgets.Widget):
        if isinstance(field, models.DateTimeField): return PreciseDateTimeWidget
        return super().widget_from_django_field(field, default=default)
    def __init__(self,*args,actor=None,**kwargs):
        self.actor=actor
        super().__init__(*args,**kwargs)
    def import_data(self,*args,**kwargs):
        kwargs.setdefault('rollback_on_validation_errors',True)
        return super().import_data(*args,**kwargs)
    def before_import(self,dataset,**kwargs):
        seen=set()
        for row in dataset.dict:
            identity=tuple(str(row.get(self.fields[name].column_name,'')).strip() for name in self._meta.import_id_fields)
            if identity and (not any(identity) or identity in seen):raise ValidationError('Missing or duplicate stable identifiers in the import file.')
            seen.add(identity)
    class Meta:
        clean_model_instances=True
        skip_unchanged=True
        report_skipped=True
        use_transactions=True
        exclude=('id',)

class BusinessTransferAdmin(ImportExportModelAdmin):
    actions = ('export_media',)
    def get_actions(self, request):
        result = super().get_actions(request)
        has_media = any(isinstance(field, models.FileField) for field in self.model._meta.fields)
        if not has_media or not self.has_export_permission(request):
            result.pop('export_media', None)
        return result
    @admin.action(description='Export selected records’ media files (.zip)')
    def export_media(self, request, queryset):
        if not self.has_export_permission(request):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        paths = set()
        for obj in queryset:
            records = [obj]
            if obj._meta.label_lower == 'catalogue.product':
                records.extend(obj.images.all())
                records.extend(obj.documents.all())
            for record in records:
                for field in record._meta.fields:
                    if isinstance(field, models.FileField):
                        name = str(getattr(record, field.name) or '')
                        if name:
                            path = PurePosixPath(name)
                            if path.is_absolute() or '..' in path.parts or ':' in name:
                                raise ValidationError('Unsafe media filename.')
                            paths.add(name)
        output = tempfile.TemporaryFile()
        try:
            with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_STORED) as archive:
                for name in sorted(paths):
                    with default_storage.open(name, 'rb') as source, archive.open(name, 'w') as destination:
                        import shutil
                        shutil.copyfileobj(source, destination)
            output.seek(0)
            return FileResponse(output, as_attachment=True, filename=f'{self.model._meta.model_name}-media.zip')
        except Exception:
            output.close()
            raise
    def get_import_formats(self):return FORMATS
    def get_export_formats(self):return FORMATS
    def has_import_permission(self,request):
        return request.user.is_superuser or (request.user.has_perm('core.import_business_data') and self.has_add_permission(request) and self.has_change_permission(request))
    def has_export_permission(self,request):
        return request.user.is_superuser or (request.user.has_perm('core.export_business_data') and self.has_view_permission(request))
    def get_import_resource_kwargs(self,request,**kwargs):
        result=super().get_import_resource_kwargs(request,**kwargs)
        result['actor']=request.user
        return result

class BusinessExportAdmin(ExportMixin, admin.ModelAdmin):
    def get_export_formats(self):return FORMATS
    def has_export_permission(self,request):
        return request.user.is_superuser or (request.user.has_perm('core.export_business_data') and self.has_view_permission(request))

class SiteSettingsResource(BusinessResource):
    logo=fields.Field(attribute='logo',widget=MediaPathWidget())
    favicon=fields.Field(attribute='favicon',widget=MediaPathWidget())
    default_social_image=fields.Field(attribute='default_social_image',widget=MediaPathWidget())
    def get_instance(self,instance_loader,row):return SiteSettings.objects.first()
    def before_import(self,dataset,**kwargs):
        if len(dataset)!=1:raise ValidationError('Site settings imports must contain exactly one record.')
    class Meta(BusinessResource.Meta):
        model=SiteSettings
        import_id_fields=()
