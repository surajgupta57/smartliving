from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils.text import slugify
import uuid


class ContentPage(models.Model):
    KINDS = [("solution", "Solution"), ("space", "Space"), ("service", "Service"), ("project", "Project case study"), ("project_guide", "Project planning guide"), ("technology", "Technology"), ("insight", "Insight article")]
    kind = models.CharField(max_length=20, choices=KINDS)
    title = models.CharField(max_length=180)
    slug = models.SlugField()
    intro = models.CharField(max_length=320, blank=True)
    body = models.TextField(blank=True)
    hero_image = models.ImageField(upload_to="pages/", blank=True)
    card_image = models.ImageField(upload_to="pages/", blank=True)
    cta_label = models.CharField(max_length=60, blank=True)
    cta_url = models.CharField(max_length=300, blank=True, help_text="Internal path or verified https URL.")
    is_published = models.BooleanField(default=False)
    display_order = models.PositiveIntegerField(default=0)
    meta_title = models.CharField(max_length=70, blank=True)
    meta_description = models.CharField(max_length=160, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (("kind", "slug"),)
        ordering = ("display_order", "title")

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        route = {"solution": "cms:solution_detail", "space": "cms:space_detail", "service": "cms:service_detail", "project": "cms:project_detail", "project_guide": "cms:project_detail", "insight": "cms:insight_detail"}.get(self.kind)
        return reverse(route, kwargs={"slug": self.slug}) if route else reverse("cms:technology")

    def __str__(self):
        return f"{self.get_kind_display()}: {self.title}"


class HomeSection(models.Model):
    transfer_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    TYPES = [(key, label) for key, label in [("hero_fullscreen", "Fullscreen hero"), ("hero_split", "Split hero"), ("hero_carousel", "Hero carousel"), ("trust_bar", "Trust bar"), ("intro_editorial", "Editorial intro"), ("category_grid", "Category grid"), ("product_grid", "Product grid"), ("featured_products", "Featured products"), ("image_text", "Image and text"), ("feature_grid", "Feature grid"), ("scene_demo", "Scene demo"), ("services_grid", "Services grid"), ("project_gallery", "Project gallery"), ("brand_grid", "Brand grid"), ("process_steps", "Process steps"), ("testimonial_slider", "Testimonials"), ("faq_accordion", "FAQ accordion"), ("promotional_banner", "Promotional banner"), ("newsletter", "Newsletter"), ("cta_banner", "CTA banner"), ("contact_form", "Contact form")]]
    section_type = models.CharField(max_length=30, choices=TYPES)
    heading = models.CharField(max_length=180, blank=True)
    eyebrow = models.CharField(max_length=80, blank=True)
    body = models.TextField(blank=True)
    desktop_image = models.ImageField(upload_to="homepage/", blank=True)
    mobile_image = models.ImageField(upload_to="homepage/", blank=True)
    cta_label = models.CharField(max_length=60, blank=True)
    cta_url = models.CharField(max_length=300, blank=True)
    theme_variant = models.CharField(max_length=20, choices=[("dark", "Dark"), ("light", "Light"), ("accent", "Accent")], default="light")
    columns = models.PositiveSmallIntegerField(default=3)
    overlay_opacity = models.PositiveSmallIntegerField(default=35)
    spacing = models.CharField(max_length=20, choices=[("compact", "Compact"), ("normal", "Normal"), ("generous", "Generous")], default="normal")
    animation = models.CharField(max_length=20, choices=[("none", "None"), ("fade", "Fade"), ("rise", "Rise")], default="fade")
    config = models.JSONField(default=dict, blank=True, help_text="Validated, template-specific content only. No HTML, CSS, or JavaScript.")
    is_enabled = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("display_order", "pk")

    def clean(self):
        if not isinstance(self.config, dict):
            raise ValidationError({"config": "Configuration must be an object."})
        if self.overlay_opacity > 90:
            raise ValidationError({"overlay_opacity": "Use a value between 0 and 90."})
        if any(key.lower() in {"html", "css", "javascript", "script"} for key in self.config):
            raise ValidationError({"config": "Executable or raw markup configuration is not permitted."})

    def __str__(self):
        return f"{self.display_order}: {self.get_section_type_display()}"


class FAQ(models.Model):
    transfer_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    question = models.CharField(max_length=240)
    answer = models.TextField()
    is_published = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)
    class Meta: ordering = ("display_order", "pk")
    def __str__(self): return self.question
