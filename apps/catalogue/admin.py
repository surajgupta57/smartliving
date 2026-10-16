from django.contrib import admin
from django.utils.html import format_html
from .models import Brand, Category, Product, ProductDocument, ProductFeature, ProductImage, ProductSpecification, ProductCompatibility
from apps.core.data_transfer import BusinessTransferAdmin
from .resources import ProductResource, BrandResource, CategoryResource, ImageResource, SpecificationResource, FeatureResource, DocumentResource
from .models import ProductPlanningProfile


class PlanningProfileInline(admin.StackedInline):
    model = ProductPlanningProfile
    extra = 0
    max_num = 1


class SpecificationInline(admin.TabularInline):
    model = ProductSpecification
    extra = 1


class FeatureInline(admin.TabularInline):
    model = ProductFeature
    extra = 1


class ImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    readonly_fields = ("preview",)
    fields = ("image", "preview", "alt_text", "caption", "image_type", "is_primary", "sort_order", "is_demo")

    @admin.display(description="Preview")
    def preview(self, obj):
        return format_html('<img src="{}" style="height:46px;border-radius:4px">', obj.image.url) if obj and obj.image else "—"


class DocumentInline(admin.TabularInline):
    model = ProductDocument
    extra = 0


class CompatibilityInline(admin.StackedInline):
    model = ProductCompatibility
    fk_name = "product"
    autocomplete_fields = ("companion",)
    extra = 0


@admin.register(Product)
class ProductAdmin(BusinessTransferAdmin):
    resource_classes = [ProductResource]
    list_display = ("thumbnail", "name", "brand", "primary_category", "price_display_mode", "is_published", "is_featured", "is_demo", "updated_at")
    list_filter = ("is_published", "is_active", "is_featured", "is_new", "is_popular", "is_demo", "brand", "primary_category", "price_display_mode", "stock_status")
    search_fields = ("name", "sku", "model_number", "brand__name")
    prepopulated_fields = {"slug": ("name",)}
    filter_horizontal = ("additional_categories",)
    list_editable = ("is_published", "is_featured")
    inlines = (SpecificationInline, FeatureInline, ImageInline, DocumentInline, CompatibilityInline, PlanningProfileInline)
    readonly_fields = ("created_at", "updated_at", "source_key", "source_checked_at")
    fieldsets = (("Identity", {"fields": ("name", "slug", "sku", "model_number", "brand", "primary_category", "additional_categories", "display_order")}), ("Customer content", {"fields": ("short_description", "full_description", "key_features", "applications", "compatibility_information", "warranty_information", "installation_required")}), ("Commerce display", {"fields": ("price_display_mode", "price", "starting_price", "currency", "stock_status", "availability_label")}), ("Publication", {"fields": ("is_active", "is_published", "is_featured", "is_new", "is_popular", "is_demo", "featured_image")}), ("SEO", {"fields": ("meta_title", "meta_description")}), ("Manufacturer provenance", {"fields": ("source_key", "source_url", "source_checked_at")}), ("Dates", {"fields": ("published_at", "created_at", "updated_at")}))

    @admin.display(description="Image")
    def thumbnail(self, obj):
        image = obj.public_image
        return format_html('<img src="{}" style="height:44px;width:56px;object-fit:cover;border-radius:4px">', image.url) if image else "—"

    @admin.action(description="Publish selected products")
    def publish_selected(self, request, queryset):
        queryset.update(is_published=True)
    actions = ("publish_selected", "export_media")


@admin.register(Category)
class CategoryAdmin(BusinessTransferAdmin):
    resource_classes = [CategoryResource]
    list_display = ("name", "parent", "display_order", "is_featured", "is_published")
    list_filter = ("is_published", "is_active", "is_featured")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Brand)
class BrandAdmin(BusinessTransferAdmin):
    resource_classes = [BrandResource]
    list_display = ("name", "is_published", "is_active", "display_order")
    list_filter = ("is_published", "is_active")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(ProductImage)
class ProductImageAdmin(BusinessTransferAdmin):
    resource_classes = [ImageResource]
    list_display = ("product", "image_type", "is_primary", "sort_order", "is_demo")
    list_filter = ("image_type", "is_demo")

@admin.register(ProductSpecification)
class SpecificationAdmin(BusinessTransferAdmin):
    resource_classes = [SpecificationResource]
    list_display = ("product", "group", "name", "is_verified")
    search_fields = ("product__name", "product__sku", "name", "value")
    list_filter = ("group", "is_verified")

@admin.register(ProductFeature)
class FeatureAdmin(BusinessTransferAdmin):
    resource_classes = [FeatureResource]
    list_display = ("product", "title", "sort_order")
    search_fields = ("product__name", "product__sku", "title")

@admin.register(ProductDocument)
class DocumentAdmin(BusinessTransferAdmin):
    resource_classes = [DocumentResource]
    list_display = ("product", "title", "visibility")
    list_filter = ("visibility", "document_type")
    search_fields = ("product__name", "title")


@admin.register(ProductCompatibility)
class CompatibilityAdmin(admin.ModelAdmin):
    list_display = ("product", "companion", "role", "is_verified", "verified_on", "is_active")
    list_filter = ("role", "is_verified", "is_active")
    search_fields = ("product__name", "companion__name", "requirements")
    autocomplete_fields = ("product", "companion")
