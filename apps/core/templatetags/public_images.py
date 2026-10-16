from django import template
from apps.core.image_variants import available

register = template.Library()


def variants(context, image):
    cache = context.render_context.setdefault('public_image_variants', {})
    key = getattr(image, 'name', '')
    if key not in cache:
        cache[key] = available(image)
    return cache[key]


@register.simple_tag(takes_context=True)
def image_url(context, image, width=720):
    choices = variants(context, image)
    if choices:
        selected = next((item for item in choices if item['width'] >= int(width)), choices[-1])
        return selected['url']
    return image.url if image else ''


@register.simple_tag(takes_context=True)
def image_srcset(context, image):
    return ', '.join(f"{item['url']} {item['width']}w" for item in variants(context, image))
