from django.db import migrations

def group_categories(apps, schema_editor):
    Category = apps.get_model('catalogue', 'Category')
    root, _ = Category.objects.get_or_create(slug='cctv-surveillance', defaults={'name': 'CCTV & Surveillance', 'is_active': True, 'is_published': True, 'is_featured': True, 'display_order': 3})
    cameras, _ = Category.objects.get_or_create(slug='cctv-cameras', defaults={'name': 'Cameras', 'parent': root, 'is_active': True, 'is_published': True, 'display_order': 1})
    Category.objects.filter(slug__in=['cctv-ip-cameras', 'hd-analog-cctv-cameras', 'dome-and-turret-cameras', 'bullet-cameras', 'ptz-cameras', 'wi-fi-and-4g-cameras']).update(parent=cameras, is_featured=False)
    Category.objects.filter(slug__in=['nvr-and-dvr-recorders', 'cctv-kits-and-recording-systems', 'cctv-accessories']).update(parent=root, is_featured=False)

class Migration(migrations.Migration):
    dependencies = [('catalogue', '0003_alter_product_slug')]
    operations = [migrations.RunPython(group_categories, migrations.RunPython.noop)]
