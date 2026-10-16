"""Product files are private on disk; every URL is served through access checks."""
import os
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.urls import reverse
from django.utils.deconstruct import deconstructible


@deconstructible
class ProductDocumentStorage(FileSystemStorage):
    @property
    def base_location(self):
        return str(settings.PRIVATE_DOCUMENT_ROOT)

    @property
    def location(self):
        return os.path.abspath(self.base_location)

    @property
    def file_permissions_mode(self):
        return 0o600

    @property
    def directory_permissions_mode(self):
        return 0o700

    def url(self, name):
        return reverse('catalogue:product_document', kwargs={'name': name})
