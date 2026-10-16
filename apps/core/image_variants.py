"""Offline responsive image copies; originals and database names remain unchanged."""
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile

from django.conf import settings
from PIL import Image, ImageOps

WIDTHS = (360, 720, 1440)


def locations(image):
    root = Path(settings.MEDIA_ROOT).resolve()
    source = Path(image.path).resolve()
    if not source.is_relative_to(root) or source == root or source.is_symlink():
        raise ValueError('Only public images within MEDIA_ROOT can be optimized.')
    stat = source.stat()
    identity = f'v1:{source.relative_to(root).as_posix()}:{stat.st_size}:{stat.st_mtime_ns}'
    key = hashlib.sha256(identity.encode()).hexdigest()
    relative = Path('optimized/images/v1') / key[:2]
    folder = root / relative
    if folder.resolve() != folder:
        raise ValueError('Optimized image directories must not contain symlinks.')
    return source, folder, relative, key


def available(image):
    if not image:
        return []
    try:
        _, folder, relative, key = locations(image)
        metadata = json.loads((folder / f'{key}.json').read_text(encoding='utf-8'))
        results = []
        for entry in metadata['variants']:
            name = entry['name']
            if Path(name).name != name or not name.startswith(key + '-') or not name.endswith('.webp'):
                continue
            file = folder / name
            if file.is_file() and not file.is_symlink():
                results.append({**entry, 'url': image.storage.url((relative / name).as_posix())})
        if metadata.get('original_width') and not any(item['width'] == metadata['original_width'] for item in results):
            results.append({'width': metadata['original_width'], 'height': metadata['original_height'],
                            'url': image.url, 'original': True})
        return sorted(results, key=lambda item: item['width'])
    except (OSError, ValueError, TypeError, KeyError, NotImplementedError, AttributeError):
        return []


def atomic_write(path, data):
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        try:
            handle.write(data)
            handle.flush()
            os.fchmod(handle.fileno(), 0o644) if hasattr(os, 'fchmod') else None
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def generate(image, dry_run=False):
    source, folder, relative, key = locations(image)
    metadata_path = folder / f'{key}.json'
    if metadata_path.is_file():
        metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
        if len([item for item in available(image) if not item.get('original')]) == len(metadata.get('variants', [])):
            return {'status': 'cached', 'original': source.stat().st_size, 'variants': metadata['variants']}
    original_size = source.stat().st_size
    with Image.open(source) as original:
        if original.format not in {'JPEG', 'PNG', 'WEBP'} or getattr(original, 'is_animated', False):
            return {'status': 'unsupported', 'original': original_size, 'variants': []}
        oriented = ImageOps.exif_transpose(original)
        oriented.load()
        if oriented.mode not in ('RGB', 'RGBA'):
            oriented = oriented.convert('RGBA' if 'transparency' in original.info else 'RGB')
        variants = []
        for width in sorted({min(width, oriented.width) for width in WIDTHS}):
            resized = oriented.copy()
            if width < resized.width:
                resized.thumbnail((width, max(1, round(oriented.height * width / oriented.width))), Image.Resampling.LANCZOS)
            output = io.BytesIO()
            options = {'icc_profile': original.info['icc_profile']} if original.info.get('icc_profile') else {}
            resized.save(output, 'WEBP', lossless=True, exact=True, method=4, **options)
            data = output.getvalue()
            if len(data) >= original_size:
                continue
            with Image.open(io.BytesIO(data)) as check:
                check.verify()
            name = f'{key}-{resized.width}.webp'
            variants.append({'name': name, 'width': resized.width, 'height': resized.height, 'bytes': len(data)})
            if not dry_run:
                # Grant public access only to generated public-image folders.
                for directory in [Path(settings.MEDIA_ROOT).resolve() / 'optimized', folder.parent.parent, folder.parent, folder]:
                    if directory.is_symlink():
                        raise ValueError('Refusing a symlink in generated image storage.')
                    directory.mkdir(exist_ok=True)
                    os.chmod(directory, 0o755)
                atomic_write(folder / name, data)
    if not dry_run:
        folder.mkdir(parents=True, exist_ok=True)
        atomic_write(metadata_path, json.dumps({'variants': variants, 'original_width': oriented.width,
                                               'original_height': oriented.height}).encode())
    return {'status': 'generated', 'original': original_size, 'variants': variants}
