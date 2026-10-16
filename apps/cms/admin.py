from django.contrib import admin
from .models import ContentPage, FAQ, HomeSection
from apps.core.data_transfer import BusinessTransferAdmin
from .resources import ContentPageResource, FAQResource, HomeSectionResource


@admin.register(ContentPage)
class ContentPageAdmin(BusinessTransferAdmin):
    resource_classes = [ContentPageResource]
    list_display = ("title", "kind", "is_published", "display_order", "updated_at")
    list_filter = ("kind", "is_published")
    search_fields = ("title", "intro", "body")
    list_editable = ("is_published", "display_order")
    prepopulated_fields = {"slug": ("title",)}


@admin.register(HomeSection)
class HomeSectionAdmin(BusinessTransferAdmin):
    resource_classes = [HomeSectionResource]
    list_display = ("section_type", "display_order", "heading", "is_enabled", "theme_variant")
    list_editable = ("display_order", "is_enabled")
    list_filter = ("section_type", "is_enabled", "theme_variant")


@admin.register(FAQ)
class FAQAdmin(BusinessTransferAdmin):
    resource_classes = [FAQResource]
    list_display = ("question", "is_published", "display_order")
    list_editable = ("is_published", "display_order")
