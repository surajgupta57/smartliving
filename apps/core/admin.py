from django.contrib import admin
from .models import SiteSettings
from .data_transfer import BusinessTransferAdmin, SiteSettingsResource


@admin.register(SiteSettings)
class SiteSettingsAdmin(BusinessTransferAdmin):
    resource_classes = [SiteSettingsResource]
    def has_import_permission(self, request):
        return request.user.is_superuser or (request.user.has_perm("core.import_business_data") and self.has_change_permission(request))
    fieldsets = (("Identity", {"fields": ("company_name", "tagline", "public_url", "logo", "favicon")}), ("Contact", {"fields": ("email", "phone", "whatsapp_number", "address", "business_hours")}), ("Appearance", {"fields": ("theme", "primary_colour", "accent_colour", "font_pair", "announcement")}), ("SEO", {"fields": ("default_meta_title", "default_meta_description", "default_social_image")}), ("Features", {"fields": ("show_whatsapp",)}))

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()
