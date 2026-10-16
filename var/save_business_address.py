from django.db import transaction
from apps.core.models import SiteSettings
with transaction.atomic():
    site = SiteSettings.objects.select_for_update().first()
    if site is None:
        raise RuntimeError('Existing site settings record is missing.')
    site.address = 'Padrauna, Kushinagar, Uttar Pradesh, 274304'
    site.save(update_fields=['address'])
print('Business address saved and verified:', SiteSettings.objects.get(pk=site.pk).address)
