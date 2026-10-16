import mimetypes
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe
from .models import ProductDocument


@require_safe
@never_cache
def product_document(request, name):
    documents = ProductDocument.objects.filter(file=name)
    staff_access = request.user.is_authenticated and request.user.is_staff and request.user.has_perm('catalogue.view_productdocument')
    document = documents.first() if staff_access else documents.filter(visibility='public', product__is_active=True, product__is_published=True).first()
    if document is None:
        # Do not disclose whether a hidden product or staff document exists.
        raise Http404
    try:
        handle = document.file.open('rb')
    except (OSError, ValueError):
        raise Http404 from None
    content_type = mimetypes.guess_type(document.file.name)[0] or 'application/octet-stream'
    # Downloads avoid executing HTML/SVG content on the application origin.
    response = FileResponse(handle, as_attachment=True, filename=document.file.name.rsplit('/', 1)[-1], content_type=content_type)
    response['X-Content-Type-Options'] = 'nosniff'
    return response
