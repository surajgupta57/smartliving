import io
from pathlib import Path
import tempfile
from contextlib import redirect_stdout
from unittest import TestCase

from PIL import Image
from scripts.compress_uploaded_media import apply_file, main, optimize


class MediaCompressionTests(TestCase):
    def png(self):
        stream = io.BytesIO()
        Image.new('RGBA', (300, 200), (10, 80, 150, 100)).save(stream, 'PNG', compress_level=0)
        return stream.getvalue()

    def test_png_gets_smaller_without_changing_pixels_or_dimensions(self):
        original = self.png()
        candidate, reason = optimize(original)
        self.assertLess(len(candidate), len(original))
        with Image.open(io.BytesIO(original)) as before, Image.open(io.BytesIO(candidate)) as after:
            self.assertEqual(before.size, after.size)
            self.assertEqual(before.convert('RGBA').tobytes(), after.convert('RGBA').tobytes())

    def test_jpeg_is_not_lossily_reencoded_without_jpegtran(self):
        stream = io.BytesIO()
        Image.new('RGB', (100, 100), 'red').save(stream, 'JPEG')
        result, reason = optimize(stream.getvalue())
        self.assertIsNone(result)
        self.assertIn('jpegtran', reason)

    def test_animated_webp_is_not_modified(self):
        stream = io.BytesIO()
        Image.new('RGB', (50, 50), 'red').save(stream, 'WEBP', save_all=True,
            append_images=[Image.new('RGB', (50, 50), 'blue')], duration=100)
        self.assertEqual(optimize(stream.getvalue()), (None, 'animated'))

    def test_dry_run_creates_no_backup_and_preserves_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            media = root / 'media'
            media.mkdir()
            image = media / 'camera.png'
            original = self.png()
            image.write_bytes(original)
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(['--media-root', str(media), '--backup-root', str(root / 'backups')]), 0)
            self.assertEqual(image.read_bytes(), original)
            self.assertFalse((root / 'backups').exists())

    def test_apply_verifies_backup_and_preserves_filename(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / 'camera.png'
            original = self.png()
            image.write_bytes(original)
            before = image.stat()
            candidate, _ = optimize(original)
            apply_file(image, candidate, before, root / 'backup', Path('camera.png'), original)
            self.assertEqual(image.read_bytes(), candidate)
            self.assertEqual((root / 'backup/originals/camera.png').read_bytes(), original)

    def test_changed_source_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / 'camera.png'
            original = self.png()
            image.write_bytes(original)
            before = image.stat()
            image.write_bytes(b'new upload')
            with self.assertRaisesRegex(ValueError, 'Source changed'):
                apply_file(image, b'candidate', before, root / 'backups', Path('camera.png'), original)
            self.assertEqual(image.read_bytes(), b'new upload')
