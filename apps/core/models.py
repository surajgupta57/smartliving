from django.core.validators import RegexValidator
from django.db import models

hex_color = RegexValidator(r"^#[0-9A-Fa-f]{6}$", "Use a six-digit hex colour, for example #B99A69.")


class RequestLimit(models.Model):
    """Short-lived counters shared by all application workers; no raw IPs."""
    key = models.CharField(max_length=64, primary_key=True)
    window = models.BigIntegerField(db_index=True)
    attempts = models.PositiveIntegerField(default=0)


class SiteSettings(models.Model):
    THEME_CHOICES = [("midnight", "Midnight and champagne"), ("sage", "Sage and ivory"), ("custom", "Validated custom colours")]
    company_name = models.CharField(max_length=120, default="Smart Living Technologies")
    tagline = models.CharField(max_length=180, default="Intelligent spaces. Protected lives.")
    public_url = models.URLField(default="https://smartliving.seas-india.com", help_text="Canonical public subdomain; update after DNS is live.")
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    whatsapp_number = models.CharField(max_length=20, blank=True, help_text="Digits with country code, e.g. 919876543210.")
    address = models.TextField(blank=True)
    business_hours = models.CharField(max_length=180, blank=True)
    announcement = models.CharField(max_length=250, blank=True)
    logo = models.ImageField(upload_to="site/", blank=True)
    favicon = models.ImageField(upload_to="site/", blank=True)
    default_social_image = models.ImageField(upload_to="site/", blank=True)
    theme = models.CharField(max_length=20, choices=THEME_CHOICES, default="midnight")
    primary_colour = models.CharField(max_length=7, default="#111315", validators=[hex_color])
    accent_colour = models.CharField(max_length=7, default="#B99A69", validators=[hex_color])
    font_pair = models.CharField(max_length=80, default="Manrope / Georgia")
    default_meta_title = models.CharField(max_length=70, blank=True)
    default_meta_description = models.CharField(max_length=160, blank=True)
    show_whatsapp = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Site settings"
        verbose_name_plural = "Site settings"
        permissions = [("import_business_data", "Can import business data"), ("export_business_data", "Can export business data")]

    def __str__(self):
        return self.company_name

    @classmethod
    def load(cls):
        return cls.objects.first() or cls.objects.create()
