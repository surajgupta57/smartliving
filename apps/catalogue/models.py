from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from .document_storage import ProductDocumentStorage
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify


class Publishable(models.Model):
    is_active = models.BooleanField(default=True)
    is_published = models.BooleanField(default=False)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        abstract = True


class Brand(Publishable):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True, blank=True)
    logo = models.ImageField(upload_to="brands/", blank=True)
    website = models.URLField(blank=True)
    description = models.TextField(blank=True)
    meta_title = models.CharField(max_length=70, blank=True)
    meta_description = models.CharField(max_length=160, blank=True)

    class Meta:
        ordering = ("display_order", "name")

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Category(Publishable):
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="children")
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True)
    icon = models.CharField(max_length=60, blank=True, help_text="Optional accessible icon label.")
    image = models.ImageField(upload_to="categories/", blank=True)
    description = models.TextField(blank=True)
    is_featured = models.BooleanField(default=False)
    meta_title = models.CharField(max_length=70, blank=True)
    meta_description = models.CharField(max_length=160, blank=True)

    class Meta:
        ordering = ("display_order", "name")
        verbose_name_plural = "categories"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Product(Publishable):
    PRICE_EXACT, PRICE_STARTING, PRICE_QUOTE, PRICE_CONTACT = "exact", "starting", "quote", "contact"
    PRICE_CHOICES = [(PRICE_EXACT, "Show exact price"), (PRICE_STARTING, "Show starting price"), (PRICE_QUOTE, "Request a quote"), (PRICE_CONTACT, "Contact for availability")]
    STOCK_CHOICES = [("in_stock", "In stock"), ("on_order", "Available to order"), ("quote", "On request"), ("discontinued", "Discontinued")]
    name = models.CharField(max_length=180)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    sku = models.CharField(max_length=64, blank=True, unique=True, null=True)
    model_number = models.CharField(max_length=100, blank=True)
    brand = models.ForeignKey(Brand, null=True, blank=True, on_delete=models.SET_NULL, related_name="products")
    primary_category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="primary_products")
    additional_categories = models.ManyToManyField(Category, blank=True, related_name="additional_products")
    short_description = models.CharField(max_length=280)
    full_description = models.TextField(blank=True)
    key_features = models.TextField(blank=True, help_text="Use Feature rows below for structured highlights.")
    featured_image = models.ImageField(upload_to="products/featured/", blank=True)
    price_display_mode = models.CharField(max_length=10, choices=PRICE_CHOICES, default=PRICE_QUOTE)
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    starting_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    currency = models.CharField(max_length=3, default="INR")
    stock_status = models.CharField(max_length=20, choices=STOCK_CHOICES, default="quote")
    availability_label = models.CharField(max_length=100, blank=True)
    warranty_information = models.TextField(blank=True)
    installation_required = models.BooleanField(default=False)
    compatibility_information = models.TextField(blank=True)
    applications = models.TextField(blank=True)
    is_featured = models.BooleanField(default=False)
    is_new = models.BooleanField(default=False)
    is_popular = models.BooleanField(default=False)
    is_demo = models.BooleanField(default=False)
    meta_title = models.CharField(max_length=70, blank=True)
    meta_description = models.CharField(max_length=160, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    source_key = models.CharField(max_length=200, unique=True, null=True, blank=True, editable=False)
    source_url = models.URLField(max_length=600, blank=True)
    source_checked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("display_order", "name")
        indexes = [
            models.Index(fields=["is_active", "is_published", "display_order"]),
            models.Index(fields=["model_number"]),
            models.Index(fields=["is_active", "is_published", "-is_featured", "display_order", "name", "id"], name="catalogue_public_featured"),
            models.Index(fields=["is_active", "is_published", "name", "id"], name="catalogue_public_name"),
            models.Index(fields=["is_active", "is_published", "price", "display_order", "name", "id"], name="catalogue_public_price"),
            models.Index(fields=["is_active", "is_published", "-price", "display_order", "name", "id"], name="catalogue_public_price_desc"),
        ]

    def clean(self):
        if self.price_display_mode == self.PRICE_EXACT and self.price is None:
            raise ValidationError({"price": "Exact-price products need a price."})
        if self.price_display_mode == self.PRICE_STARTING and self.starting_price is None:
            raise ValidationError({"starting_price": "Starting-price products need a starting price."})

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        if self.is_published and not self.published_at:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("catalogue:product_detail", kwargs={"slug": self.slug})

    @property
    def public_image(self):
        cached = getattr(self, "_prefetched_objects_cache", {}).get("images")
        primary = next((image for image in cached if image.is_primary), None) if cached is not None else self.images.filter(is_primary=True).first()
        return primary.image if primary else self.featured_image

    @property
    def price_label(self):
        if self.price_display_mode == self.PRICE_EXACT:
            return f"{self.currency} {self.price:,.0f}"
        if self.price_display_mode == self.PRICE_STARTING:
            return f"From {self.currency} {self.starting_price:,.0f}"
        return "Request a quote" if self.price_display_mode == self.PRICE_QUOTE else "Contact for availability"

    def __str__(self):
        return self.name


class ProductSpecification(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="specifications")
    name = models.CharField(max_length=100)
    value = models.TextField()
    unit = models.CharField(max_length=30, blank=True)
    group = models.CharField(max_length=80, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_verified = models.BooleanField(default=False)
    class Meta:
        ordering = ("group", "sort_order", "name")
    def __str__(self):
        return f"{self.name}: {self.value} {self.unit}".strip()


class ProductFeature(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="features")
    title = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    class Meta:
        ordering = ("sort_order", "title")
    def __str__(self):
        return self.title


class ProductImage(models.Model):
    TYPES = [("main", "Main product image"), ("front", "Front view"), ("side", "Side view"), ("rear", "Rear / connectors"), ("detail", "Detail view"), ("installed", "Installed product"), ("packaging", "Packaging"), ("accessories", "Accessories"), ("lifestyle", "Lifestyle / application"), ("diagram", "Technical diagram")]
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="products/gallery/")
    alt_text = models.CharField(max_length=180, blank=True)
    caption = models.CharField(max_length=240, blank=True)
    image_type = models.CharField(max_length=20, choices=TYPES, default="detail")
    is_primary = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)
    is_demo = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ("sort_order", "id")
    def clean(self):
        if self.image and self.image.size > 8 * 1024 * 1024:
            raise ValidationError({"image": "Please keep individual images below 8 MB."})
        if self.is_primary and ProductImage.objects.filter(product=self.product, is_primary=True).exclude(pk=self.pk).exists():
            raise ValidationError({"is_primary": "Only one gallery image may be primary."})
    def __str__(self):
        return f"{self.product} — {self.get_image_type_display()}"


class ProductDocument(models.Model):
    VISIBILITY = [("public", "Public"), ("staff", "Staff only")]
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="documents")
    title = models.CharField(max_length=160)
    file = models.FileField(upload_to="products/documents/", storage=ProductDocumentStorage())
    document_type = models.CharField(max_length=30, default="datasheet")
    visibility = models.CharField(max_length=10, choices=VISIBILITY, default="public")
    sort_order = models.PositiveIntegerField(default=0)
    class Meta:
        ordering = ("sort_order", "title")
    def __str__(self):
        return self.title


class ProductCompatibility(models.Model):
    """Directional, evidence-backed pairing; never implies a complete system."""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="compatibility_links")
    companion = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="used_with_links")
    role = models.CharField(max_length=20, choices=[("recorder", "Recorder"), ("power", "PoE / power"), ("controller", "Controller / hub"), ("accessory", "Accessory"), ("other", "Other")])
    requirements = models.TextField(help_text="State supported protocols, power budget, firmware, regional variants and any limitations.")
    evidence_url = models.URLField(max_length=600, help_text="Manufacturer documentation or published test evidence.")
    verified_on = models.DateField(null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "product compatibility pairings"
        ordering = ("role", "pk")
        constraints = [models.UniqueConstraint(fields=["product", "companion"], name="unique_product_companion"), models.CheckConstraint(condition=~models.Q(product=models.F("companion")), name="compatibility_no_self")]

    def clean(self):
        errors = {}
        if self.product_id and self.product_id == self.companion_id:
            errors["companion"] = "Choose a different product."
        if self.is_verified and not self.verified_on:
            errors["verified_on"] = "Record the verification date before publishing a pairing."
        if self.verified_on and self.verified_on > timezone.localdate():
            errors["verified_on"] = "Verification cannot be in the future."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.product} / {self.companion}"


class ProductPlanningProfile(models.Model):
    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name="planning_profile")
    role = models.CharField(max_length=20, choices=[("other", "Other / unspecified"), ("camera", "Camera"), ("recorder", "Recorder"), ("poe", "PoE switch"), ("controller", "Controller / hub")], default="other")
    environment = models.CharField(max_length=10, choices=[("unknown", "Needs confirmation"), ("indoor", "Indoor only"), ("outdoor", "Outdoor only"), ("both", "Indoor and outdoor")], default="unknown")
    camera_technology = models.CharField(max_length=10, choices=[("unknown", "Needs confirmation"), ("ip", "IP / network"), ("wifi", "Wi-Fi"), ("cellular", "4G / cellular"), ("analog", "HD analog")], default="unknown")
    recorder_channels = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    poe_ports = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    poe_budget_watts = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0.01)], help_text="Total usable PoE output budget, not mains input power.")
    camera_max_poe_watts = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0.01)], help_text="Maximum PoE demand including enabled features; leave blank for non-PoE cameras.")
    evidence_url = models.URLField(max_length=600)
    verified_on = models.DateField(null=True, blank=True)
    is_verified = models.BooleanField(default=False)

    class Meta:
        verbose_name = "product planning profile"

    def clean(self):
        errors = {}
        if self.is_verified and not self.verified_on:
            errors["verified_on"] = "Record the date you checked the manufacturer data."
        if self.verified_on and self.verified_on > timezone.localdate():
            errors["verified_on"] = "Verification cannot be in the future."
        for field, role in [("recorder_channels", "recorder"), ("poe_ports", "poe"), ("poe_budget_watts", "poe"), ("camera_max_poe_watts", "camera")]:
            if getattr(self, field) is not None and self.role != role:
                errors[field] = f"This field applies only to the {role} role."
        if self.camera_technology != "unknown" and self.role != "camera":
            errors["camera_technology"] = "Choose the Camera role for this field."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return str(self.product)


class ProductSearchToken(models.Model):
    """Portable inverted index for indexed word and model-prefix lookup."""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="search_tokens")
    token = models.CharField(max_length=100)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["product", "token"], name="unique_product_search_token")]
        indexes = [models.Index(fields=["token", "product"], name="catalogue_token_lookup")]
