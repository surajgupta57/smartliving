from io import StringIO
from pathlib import Path
import tempfile
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command,CommandError
from django.test import TestCase,override_settings
from .models import Category,Product,ProductDocument


class ProductDocumentSecurityTests(TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.override=override_settings(MEDIA_ROOT=self.root/'media',PRIVATE_DOCUMENT_ROOT=self.root/'documents')
        self.override.enable()
        self.addCleanup(self.temp.cleanup);self.addCleanup(self.override.disable)
        category=Category.objects.create(name='Document audit',is_published=True)
        self.product=Product.objects.create(name='Document test',sku='DOC-AUDIT',primary_category=category,is_published=True)
        self.document=ProductDocument.objects.create(product=self.product,title='Test datasheet',file=SimpleUploadedFile('audit.pdf',b'%PDF-1.4\naudit payload'))

    def test_public_download_is_checked_attachment_and_stored_outside_media(self):
        self.assertTrue(Path(self.document.file.path).is_relative_to(self.root/'documents'))
        self.assertFalse((self.root/'media'/self.document.file.name).exists())
        self.assertTrue(self.document.file.url.startswith('/documents/'))
        response=self.client.get(self.document.file.url)
        self.assertEqual(response.status_code,200)
        self.assertIn('attachment',response['Content-Disposition'])
        self.assertEqual(response['X-Content-Type-Options'],'nosniff')
        self.assertEqual(b''.join(response.streaming_content),b'%PDF-1.4\naudit payload')
        self.assertIn('no-store',response['Cache-Control'])

    def test_staff_only_file_cannot_be_downloaded_by_anonymous_or_unprivileged_users(self):
        self.document.visibility='staff';self.document.save()
        self.assertEqual(self.client.get(self.document.file.url).status_code,404)
        user=get_user_model().objects.create_user('document-reader',is_staff=True)
        self.client.force_login(user)
        self.assertEqual(self.client.get(self.document.file.url).status_code,404)
        user.user_permissions.add(Permission.objects.get(content_type__app_label='catalogue',codename='view_productdocument'))
        response=self.client.get(self.document.file.url)
        self.assertEqual(response.status_code,200);response.close()

    def test_unpublished_product_file_and_nonstaff_reader_are_hidden(self):
        self.product.is_published=False;self.product.save()
        self.assertEqual(self.client.get(self.document.file.url).status_code,404)
        user=get_user_model().objects.create_user('notstaff')
        user.user_permissions.add(Permission.objects.get(content_type__app_label='catalogue',codename='view_productdocument'))
        self.client.force_login(user)
        self.assertEqual(self.client.get(self.document.file.url).status_code,404)

    def test_missing_file_returns_404(self):
        Path(self.document.file.path).unlink()
        self.assertEqual(self.client.get(self.document.file.url).status_code,404)

    def test_old_public_file_is_verified_moved_and_command_is_idempotent(self):
        private=Path(self.document.file.path)
        public=self.root/'media'/self.document.file.name
        public.parent.mkdir(parents=True)
        public.write_bytes(private.read_bytes());private.unlink()
        call_command('secure_product_documents',dry_run=True,stdout=StringIO())
        self.assertTrue(public.exists());self.assertFalse(private.exists())
        call_command('secure_product_documents',remove_public_copies=True,stdout=StringIO())
        self.assertFalse(public.exists());self.assertTrue(private.exists())
        call_command('secure_product_documents',remove_public_copies=True,stdout=StringIO())
        self.assertEqual(private.read_bytes(),b'%PDF-1.4\naudit payload')

    def test_document_conflict_never_deletes_public_original(self):
        public=self.root/'media'/self.document.file.name
        public.parent.mkdir(parents=True);public.write_bytes(b'different data')
        with self.assertRaises(CommandError):call_command('secure_product_documents',remove_public_copies=True,stdout=StringIO())
        self.assertTrue(public.exists())

    def test_document_downloads_are_get_only(self):
        self.assertEqual(self.client.post(self.document.file.url).status_code,405)
