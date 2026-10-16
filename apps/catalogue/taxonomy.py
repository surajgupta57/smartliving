"""CCTV navigation groups; existing leaf identities remain stable for imports and links."""
CCTV_ROOT = 'cctv-surveillance'
CAMERAS = 'cctv-cameras'
CAMERA_LEAVES = ['cctv-ip-cameras', 'hd-analog-cctv-cameras', 'dome-and-turret-cameras', 'bullet-cameras', 'ptz-cameras', 'wi-fi-and-4g-cameras']
PRODUCT_TYPES = [('', 'All CCTV products'), (CAMERAS, 'Cameras'), ('nvr-and-dvr-recorders', 'Recorders — NVR & DVR'), ('cctv-kits-and-recording-systems', 'Complete CCTV kits'), ('cctv-accessories', 'CCTV accessories')]

def descendants(category, categories):
    found = {category.slug}
    ids = {category.pk}
    while True:
        children = [item for item in categories if item.parent_id in ids and item.slug not in found]
        if not children: return found
        found.update(item.slug for item in children)
        ids.update(item.pk for item in children)

def arrange_cctv_categories(Category):
    root, _ = Category.objects.get_or_create(slug=CCTV_ROOT, defaults={'name': 'CCTV & Surveillance', 'is_active': True, 'is_published': True, 'is_featured': True, 'display_order': 3})
    cameras, _ = Category.objects.get_or_create(slug=CAMERAS, defaults={'name': 'Cameras', 'parent': root, 'is_active': True, 'is_published': True, 'display_order': 1})
    Category.objects.filter(slug__in=CAMERA_LEAVES).update(parent=cameras, is_featured=False)
    Category.objects.filter(slug__in=[value for value, _ in PRODUCT_TYPES if value and value != CAMERAS]).update(parent=root, is_featured=False)
