import os,sys,json,importlib.util
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root));os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django;django.setup()
from apps.catalogue.models import Product,ProductSpecification,ProductFeature
from django.db import transaction
spec=importlib.util.spec_from_file_location('c',Path(__file__).with_name('build_manufacturer_seed.py'));c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
path=c.OUT/'manifest.json';m=json.loads(path.read_text(encoding='utf-8'))
for r in m['products']:
 if r['brand']=='Zipato' and 'zipatile2' in r['source_url']:
  revised=c.parse_zipato(r['source_url']);old=r['specifications'];r['specifications']=revised['specifications']
  groups={row['name'].lower():row['value'] for row in r['specifications']}
  r['short_description']='Smart-home touch controller. Manufacturer lists a quad-core Cortex ARM CPU, 2 GB RAM and an 8-inch touch display.'
  r['features']=[{'title':'System platform','description':groups.get('system','')},{'title':'Sensor integration','description':groups.get('sensors','')},{'title':'Network options','description':groups.get('network','')},{'title':'Display and interfaces','description':groups.get('input/output','')}]
  r['full_description']=r['short_description']+'\n\nManufacturer specifications include system hardware, network options, sensors and power interfaces. Optional modules and regional configurations must be confirmed with your quotation.'
  p=Product.objects.get(source_key=r['key'])
  with transaction.atomic():
   p.specifications.all().delete()
   ProductSpecification.objects.bulk_create([ProductSpecification(product=p,name=s['name'],value=s['value'],group=s.get('group',''),sort_order=i,is_verified=True) for i,s in enumerate(r['specifications'])])
   ProductFeature.objects.bulk_create([ProductFeature(product=p,title=f['title'],description=f['description'],sort_order=i) for i,f in enumerate(r['features'])])
   p.short_description=r['short_description'];p.full_description=r['full_description'];p.meta_description=r['short_description'][:160];p.save(update_fields=['short_description','full_description','meta_description'])
 for f in r['features']:
  f['description']=f.get('description','').replace('【','').replace('】','')
 if not r['features']:
  rows=[s for s in r['specifications'] if s['group']!='Identity' and s['name'].lower() not in ['model','manufacturer sku','frequency']][:3]
  r['features']=[{'title':s['name'],'description':s['value']} for s in rows]
  p=Product.objects.get(source_key=r['key'])
  if not p.features.exists():ProductFeature.objects.bulk_create([ProductFeature(product=p,title=f['title'],description=f['description'],sort_order=i) for i,f in enumerate(r['features'])])
path.write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding='utf-8')
report_path=c.OUT/'report.json';report=json.loads(report_path.read_text(encoding='utf-8'));report['specifications']=sum(len(p['specifications']) for p in m['products']);report['features']=sum(len(p['features']) for p in m['products']);report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('Complete feature coverage:',sum(bool(p['features']) for p in m['products']));print('Specification rows:',report['specifications'])
