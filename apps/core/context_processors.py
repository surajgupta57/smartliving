from .models import SiteSettings
from urllib.parse import quote


def site_context(request):
    settings = SiteSettings.load()
    digits = ''.join(char for char in settings.whatsapp_number if char.isdigit())
    message = 'Hello, I would like to discuss a smart-home, CCTV or networking requirement.'
    return {
        "site_settings": settings,
        "contact_whatsapp_url": f'https://wa.me/{digits}?text={quote(message)}' if settings.show_whatsapp and digits else '',
        "quote_count": len(request.session.get("quote_products", [])),
        "compare_count": len(request.session.get("compare_products", [])),
    }
