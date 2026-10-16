import hashlib
from pathlib import Path
import tempfile
from types import SimpleNamespace

from django.core.files.storage import FileSystemStorage
from django.template import Context, Template
from django.test import SimpleTestCase, override_settings
from PIL import Image, ImageOps

from .image_variants import available, generate, locations


class ImageVariantTests(SimpleTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.settings = override_settings(MEDIA_ROOT=self.root, MEDIA_URL='/media/')
        self.settings.enable()
        self.addCleanup(self.settings.disable)
        self.storage = FileSystemStorage(location=self.root, base_url='/media/')
        self.source = self.root / 'camera.png'
        Image.new('RGBA', (1600, 1000), (30, 110, 180, 160)).save(self.source)
        self.image = SimpleNamespace(name='camera.png', path=str(self.source), storage=self.storage, url='/media/camera.png')

    def test_responsive_copies_preserve_original_and_lossless_resized_pixels(self):
        before = hashlib.sha256(self.source.read_bytes()).digest()
        result = generate(self.image)
        choices = available(self.image)
        self.assertEqual([item['width'] for item in choices], [360, 720, 1440, 1600])
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).digest(), before)
        for entry in choices:
            if entry.get('original'):
                continue
            with Image.open(self.source) as original:
                expected = ImageOps.exif_transpose(original)
                expected.thumbnail((entry['width'], round(1000 * entry['width'] / 1600)), Image.Resampling.LANCZOS)
                _, folder, _, _ = locations(self.image)
                with Image.open(folder / entry['name']) as resized:
                    self.assertEqual(resized.convert('RGBA').tobytes(), expected.convert('RGBA').tobytes())
                    self.assertLess((folder / entry['name']).stat().st_size, self.source.stat().st_size)
        self.assertEqual(result['status'], 'generated')
        self.assertEqual(generate(self.image)['status'], 'cached')

    def test_dry_run_does_not_write_and_page_falls_back_to_original(self):
        generate(self.image, dry_run=True)
        self.assertFalse((self.root / 'optimized').exists())
        self.assertEqual(available(self.image), [])
        template = Template('{% load public_images %}{% image_url image 720 %}|{% image_srcset image %}')
        self.assertEqual(template.render(Context({'image': self.image})), '/media/camera.png|')

    def test_updated_original_invalidates_old_variants_without_deleting_them(self):
        generate(self.image)
        old_folder = self.root / 'optimized'
        old_files = list(old_folder.rglob('*.webp'))
        Image.new('RGB', (900, 600), 'red').save(self.source)
        self.assertEqual(available(self.image), [])
        generate(self.image)
        self.assertTrue(available(self.image))
        self.assertTrue(all(path.exists() for path in old_files))

    def test_no_upscaling_and_template_uses_generated_urls(self):
        Image.new('RGB', (120, 80), 'blue').save(self.source)
        generate(self.image)
        self.assertEqual([entry['width'] for entry in available(self.image)], [120])
        rendered = Template('{% load public_images %}{% image_url image 720 %}').render(Context({'image': self.image}))
        self.assertIn('/media/optimized/images/v1/', rendered)

    def test_private_or_missing_images_are_not_exposed(self):
        outside = self.root.parent / 'private-image.png'
        private_image = SimpleNamespace(path=str(outside), name='../private-image.png', storage=self.storage)
        with self.assertRaises(ValueError):
            generate(private_image)
        self.assertEqual(available(private_image), [])
        self.source.unlink()
        self.assertEqual(available(self.image), [])

    def test_animated_images_are_preserved(self):
        self.source = self.root / 'animated.webp'
        Image.new('RGB', (100, 100), 'red').save(self.source, save_all=True, append_images=[Image.new('RGB', (100, 100), 'blue')], duration=100, loop=0)
        self.image.path = str(self.source)
        self.image.name = 'animated.webp'
        self.assertEqual(generate(self.image)['status'], 'unsupported')
        self.assertFalse((self.root / 'optimized').exists())
