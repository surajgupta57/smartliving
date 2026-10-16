"""Validate every seeded product against the real admin import resource, without writes."""
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from apps.catalogue.resources import ProductResource
resource = ProductResource()
dataset = resource.export()
result = resource.import_data(dataset, dry_run=True)
print('Exported products:', len(dataset), 'Totals:', result.totals)
print('Errors:', result.row_errors(), result.base_errors)
print('Validation errors:', [(row.number, row.error) for row in result.invalid_rows][:20])
if result.has_errors() or result.has_validation_errors(): raise SystemExit(1)
