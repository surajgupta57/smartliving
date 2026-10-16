"""Normalize manufacturer catalogue copy without altering staff edits."""
import os,sys,json,re
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root));os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django;django.setup()
from apps.catalogue.models import Product
path=root/'catalogue_seed/manufacturers/manifest.json';manifest=json.loads(path.read_text(encoding='utf-8'))
changed=0
for r in manifest['products']:
 old_name,old_short,old_full=r['name'],r['short_description'],r['full_description']
 if r['brand']=='Shelly':
  canonical=next((s['value'] for s in r['specifications'] if s['name'].lower().strip(':')=='device name'),'')
  r['name']=(canonical if canonical.startswith('Shelly') else re.sub(r'\s+List$', '',r['name']))[:180]
 short=r['short_description']
 if r['brand']=='SONOFF':short=short.replace('【','').replace('】',': ')
 if r['brand']=='Zipato':
  facts=[s for s in r['specifications'] if s['group'] not in ['Identity'] and s['name'].lower() not in ['weight','dimensions','frequency']]
  short='; '.join(s['name']+': '+s['value'][:100] for s in facts[:2])
 if r['brand']=='EZVIZ' and len(short)<70:
  keys=['max. resolution','resolution','image sensor','video compression','lens','wi-fi','standard','storage','max resolution']
  facts=sorted([s for s in r['specifications'] if s['name'].lower() in keys],key=lambda s:keys.index(s['name'].lower()))
  short='; '.join(s['name']+': '+s['value'][:100] for s in facts[:2]) or short
 short=re.sub(r'\s+',' ',short).strip()
 r['short_description']=short[:280]
 r['full_description']=r['short_description']+'\n\n'+r['name']+' is listed in the '+r['brand']+' manufacturer catalogue. Review the technical specifications and gallery for its published configuration.\n\nRequest a quotation to confirm the regional variant, hardware revision, compatibility, installation scope and local availability.'
 if (old_name,old_short,old_full)!=(r['name'],r['short_description'],r['full_description']):
  changed+=Product.objects.filter(source_key=r['key'],name=old_name,short_description=old_short,full_description=old_full).update(name=r['name'],short_description=r['short_description'],full_description=r['full_description'],meta_description=r['short_description'][:160])
path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print('Normalized',changed,'new source-imported records; unmatched staff edits preserved.')
