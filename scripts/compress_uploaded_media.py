#!/usr/bin/env python3
"""Standalone cPanel image compression. Dry-run by default; originals backed up on --apply.

No Django imports, resizing, lossy encoding, URL changes or database changes.
Requires Pillow in the activated app virtualenv. JPEG needs host-provided jpegtran.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import warnings

from PIL import Image, PngImagePlugin


def digest(data):
    return hashlib.sha256(data).hexdigest()


def optimize(data, jpegtran=None):
    with Image.open(io.BytesIO(data)) as source:
        if getattr(source, 'is_animated', False):
            return None, 'animated'
        if source.mode not in {'RGB', 'RGBA', 'L', 'LA', 'P'}:
            return None, 'unusual colour mode'
        source.load()
        options = {key: source.info[key] for key in ('icc_profile', 'exif', 'xmp') if source.info.get(key)}
        output = io.BytesIO()
        if source.format == 'PNG':
            if 'transparency' in source.info:
                options['transparency'] = source.info['transparency']
            if 'dpi' in source.info:
                options['dpi'] = source.info['dpi']
            text = PngImagePlugin.PngInfo()
            for key, value in getattr(source, 'text', {}).items():
                text.add_itxt(key, value)
            source.save(output, 'PNG', optimize=True, compress_level=9, pnginfo=text, **options)
            candidate = output.getvalue()
        elif source.format == 'WEBP':
            source.save(output, 'WEBP', lossless=True, exact=True, method=6, **options)
            candidate = output.getvalue()
        elif source.format == 'JPEG':
            if not jpegtran:
                return None, 'JPEG needs jpegtran for lossless optimisation'
            result = subprocess.run([jpegtran, '-copy', 'all', '-optimize', '-progressive'],
                                    input=data, capture_output=True, timeout=120, check=False)
            if result.returncode:
                raise ValueError('jpegtran failed')
            candidate = result.stdout
        else:
            return None, 'unsupported format'
        if len(candidate) >= len(data):
            return None, 'already compact'
        with Image.open(io.BytesIO(candidate)) as check:
            check.load()
            if (check.format != source.format or check.size != source.size
                    or check.convert('RGBA').tobytes() != source.convert('RGBA').tobytes()
                    or check.getexif().get(274) != source.getexif().get(274)):
                raise ValueError('Pixel, orientation or format verification failed')
        return candidate, 'smaller with identical decoded pixels'


def apply_file(path, candidate, before, backup_root, relative, original):
    current = path.stat()
    if current.st_size != before.st_size or current.st_mtime_ns != before.st_mtime_ns or path.is_symlink():
        raise ValueError('Source changed during processing; not replaced')
    backup = backup_root / 'originals' / relative
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, backup)
    os.chmod(backup, 0o600)
    if digest(backup.read_bytes()) != digest(original):
        raise ValueError('Backup verification failed; not replaced')
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.media-opt-', delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(candidate)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, stat.S_IMODE(before.st_mode) & 0o666)
        current = path.stat()
        if current.st_size != before.st_size or current.st_mtime_ns != before.st_mtime_ns or path.is_symlink():
            raise ValueError('Source changed after backup; not replaced')
        os.replace(temporary, path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--media-root', type=Path, default=Path.home() / 'public_html/smartliving/media')
    parser.add_argument('--backup-root', type=Path, default=Path.home() / 'apps/smartliving/backups/media-optimization')
    parser.add_argument('--apply', action='store_true', help='Back up and atomically replace only smaller verified images.')
    parser.add_argument('--limit', type=int, default=0, help='Process at most N images; 0 means all.')
    args = parser.parse_args(argv)
    root = args.media_root.expanduser().absolute()
    backup_base = args.backup_root.expanduser().absolute()
    if args.limit < 0 or not root.is_dir() or root.is_symlink() or (os.name == 'posix' and root.resolve() != root):
        parser.error('Use an existing real media directory and a nonnegative limit.')
    root = root.resolve()
    if (backup_base.resolve() == root or root in backup_base.resolve().parents
            or any(part.lower() in {'public_html', 'htdocs', 'httpdocs', 'www'} for part in backup_base.resolve().parts)):
        parser.error('Backup root must be private, outside public directories and media.')
    if backup_base.is_symlink() or (os.name == 'posix' and backup_base.resolve() != backup_base):
        parser.error('Backup directories must not contain symlinks.')
    backup_base = backup_base.resolve()
    if args.apply and os.name != 'posix':
        parser.error('--apply must run on the Linux hosting account; local dry-run/tests are supported.')
    previous_umask = os.umask(0o077)
    lock = None
    try:
        if args.apply:
            import fcntl
            backup_base.mkdir(parents=True, exist_ok=True)
            lock = (backup_base / 'optimization.lock').open('a')
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                parser.error('Another media optimisation is running.')
        destination = backup_base / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        manifest = destination / 'manifest.jsonl'
        jpegtran = shutil.which('jpegtran')
        processed = changed = errors = saved = 0
        skipped = {}
        for directory, folders, files in os.walk(root, followlinks=False):
            folders[:] = sorted(name for name in folders if not name.startswith('.') and name != 'optimized'
                                and not (Path(directory) / name).is_symlink())
            for filename in sorted(files):
                path = Path(directory) / filename
                if filename.startswith('.') or path.is_symlink() or path.suffix.lower() not in {'.png', '.jpg', '.jpeg', '.webp'}:
                    continue
                if args.limit and processed >= args.limit:
                    break
                processed += 1
                relative = path.relative_to(root)
                try:
                    before = path.stat()
                    data = path.read_bytes()
                    with warnings.catch_warnings():
                        warnings.simplefilter('error', Image.DecompressionBombWarning)
                        candidate, reason = optimize(data, jpegtran)
                    if candidate is None:
                        skipped[reason] = skipped.get(reason, 0) + 1
                        continue
                    record = {'path': relative.as_posix(), 'before': len(data), 'after': len(candidate),
                              'original_sha256': digest(data), 'optimized_sha256': digest(candidate)}
                    if args.apply:
                        destination.mkdir(exist_ok=True)
                        # Record recovery information before any replacement.
                        with manifest.open('a', encoding='utf-8') as handle:
                            handle.write(json.dumps(record) + '\n')
                            handle.flush()
                            os.fsync(handle.fileno())
                        apply_file(path, candidate, before, destination, relative, data)
                    changed += 1
                    saved += len(data) - len(candidate)
                    print(f'{"Optimized" if args.apply else "Would optimize"}: {relative} ({len(data):,} -> {len(candidate):,} bytes)', flush=True)
                except Exception as exc:
                    errors += 1
                    print(f'Skipped {relative}: {type(exc).__name__}', flush=True)
            if args.limit and processed >= args.limit:
                break
        print(f'Images checked: {processed}; smaller: {changed}; errors: {errors}; savings: {saved / 1048576:.2f} MiB.')
        for reason, count in skipped.items():
            print(f'Skipped {count}: {reason}.')
        print('Dry run only. Use --apply to save with private backups.' if not args.apply else f'Original backups, if files changed: {destination}')
        print('Image URLs and dimensions unchanged. PDFs/videos/private documents were not modified.')
        return 1 if errors else 0
    finally:
        if lock:
            lock.close()
        os.umask(previous_umask)


if __name__ == '__main__':
    raise SystemExit(main())
