import os,sys,json,re,importlib.util
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root));os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django;django.setup()
from apps.catalogue.models import Product,ProductSpecification,ProductFeature
spec=importlib.util.spec_from_file_location('c',Path(__file__).with_name('build_manufacturer_seed.py'));c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
path=c.OUT/'manifest.json';m=json.loads(path.read_text(encoding='utf-8'));original={p['key']:p for p in json.loads((c.OUT/'records.json').read_text(encoding='utf-8'))}
for r in m['products']:
 if r['brand']=='Zipato' and not r['short_description']:
  source=original[r['key']]['short_description']
  match=re.search(r'Quad Core\s*([0-9.]+)\s*GHz',source,re.I)
  processor='Quad-core '+match.group(1)+' GHz CPU' if match else 'Manufacturer-listed modular controller'
  s=c.soup_url(r['source_url']);tab=s.select_one('#tab-description')
  modules=[c.text(h) for h in tab.select('h2') if c.text(h).endswith('Module')]
  extra=[{'name':'Processor','value':processor,'group':'System'},{'name':'Optional expansion modules','value':', '.join(modules),'group':'Compatibility'}]
  r['specifications']+=extra
  r['features']+=[{'title':processor,'description':'Processor information from the manufacturer product description.'},{'title':'Optional module expansion','description':'Manufacturer lists '+', '.join(modules)+'. Modules are separate options; confirm the selected configuration.'}]
  r['short_description']='Modular smart-home controller with a '+processor.lower()+'. Optional expansion modules are available for the configurations listed by the manufacturer.'
  r['full_description']=r['short_description']+'\n\nOptional expansion modules: '+', '.join(modules)+'. Review the source specifications and request a quotation to confirm regional configuration and availability.'
  p=Product.objects.get(source_key=r['key'])
  if not p.short_description:
   p.short_description=r['short_description'];p.full_description=r['full_description'];p.meta_description=r['short_description'][:160];p.save(update_fields=['short_description','full_description','meta_description'])
   for row in extra:ProductSpecification.objects.get_or_create(product=p,name=row['name'],defaults={'value':row['value'],'group':row['group'],'is_verified':True})
   for f in r['features'][-2:]:ProductFeature.objects.get_or_create(product=p,title=f['title'],defaults={'description':f['description']})
path.write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding='utf-8')
report_path=c.OUT/'report.json';report=json.loads(report_path.read_text(encoding='utf-8'));report['specifications']=sum(len(p['specifications']) for p in m['products']);report['features']=sum(len(p['features']) for p in m['products']);report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('All descriptions present:',all(p['short_description'] for p in m['products']))
