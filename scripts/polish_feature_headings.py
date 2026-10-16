"""Separate source feature labels from their descriptions, preserving staff changes."""
import os, sys, json
from pathlib import Path
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root)); os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from apps.catalogue.models import ProductFeature
path = root / 'catalogue_seed/manufacturers/manifest.json'
manifest = json.loads(path.read_text(encoding='utf-8'))
changed = 0
for product in manifest['products']:
    for feature in product['features']:
        old_title, old_description = feature['title'], feature.get('description', '')
        complete = old_description or old_title
        label, separator, description = complete.partition(':')
        if separator and 2 <= len(label) <= 70:
            feature['title'] = label.strip()
            feature['description'] = description.strip()
        elif len(old_title) > 75:
            feature['title'] = ' '.join(old_title.split()[:8]).rstrip('.,;') + '…'
            feature['description'] = complete
        if (old_title, old_description) != (feature['title'], feature['description']):
            changed += ProductFeature.objects.filter(product__source_key=product['key'], title=old_title, description=old_description).update(title=feature['title'], description=feature['description'])
path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
print('Polished feature headings:', changed)
