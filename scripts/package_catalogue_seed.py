"""Package only referenced catalogue assets and the application changes needed to deploy them."""
import json,hashlib,zipfile
from pathlib import Path
root=Path(__file__).resolve().parents[1];bundle=root/'catalogue_seed/manufacturers'
manifest=json.loads((bundle/'manifest.json').read_text(encoding='utf-8'))
if manifest['product_count']!=500:raise SystemExit('Refusing to package an incomplete catalogue')
files={bundle/name for name in ['manifest.json','report.json','README.md']}
for p in manifest['products']:
 for a in p['images']+p['documents']:files.add(bundle/a['path'])
for app in ['catalogue','core','cms','leads']:
 files.update(p for p in (root/'apps'/app).rglob('*.py') if '__pycache__' not in p.parts)
files.update(p for p in (root/'templates').rglob('*.html'))
files.update(p for p in (root/'static').rglob('*') if p.is_file())
files.update(root/name for name in ['config/settings.py','config/urls.py','requirements.txt','ADMIN_DATA_TRANSFER.md'])
for name in ['build_manufacturer_seed.py','finalize_manufacturer_seed.py','expand_shelly.py','expand_ezviz.py','expand_cpplus.py','discover_tplink.py','audit_seed_categories.py','package_catalogue_seed.py']:files.add(root/'scripts'/name)
archive=root/'smartliving-catalogue-500.zip'
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_STORED) as output:
 for path in sorted(files):output.write(path,path.relative_to(root).as_posix())
sha=hashlib.sha256(archive.read_bytes()).hexdigest()
archive.with_suffix('.sha256').write_text(sha+'  '+archive.name+'\n',encoding='utf-8')
print('Archive:',archive)
print('File count:',len(files),'MB:',round(archive.stat().st_size/1024/1024,1),'SHA256:',sha)
