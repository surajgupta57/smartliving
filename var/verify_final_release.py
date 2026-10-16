from pathlib import Path
import hashlib, zipfile
root=Path.cwd()
release=root/'deploy/releases/smartliving-production.zip'
expected=release.with_suffix('.sha256').read_text().split()[0]
assert hashlib.sha256(release.read_bytes()).hexdigest()==expected
with zipfile.ZipFile(release) as archive:
    assert archive.testzip() is None
    names=set(archive.namelist())
    assert {'docs/PRODUCTION_LAUNCH.md','docs/PRODUCTION_READINESS.md','apps/catalogue/migrations/0011_private_product_document_storage.py'} <= names
    assert not any(name.startswith(('var/','media/','.venv/','output/')) for name in names)
    assert not any(Path(name).name.startswith('.env') and name!='.env.production.example' for name in names)
print('Final release verified: ZIP integrity, SHA256, required files and private-data exclusions passed.')
