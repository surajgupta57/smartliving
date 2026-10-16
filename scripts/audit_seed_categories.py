"""Audit categories in the final portable seed; never invent product content."""
import importlib.util,json
from pathlib import Path
from collections import Counter
spec=importlib.util.spec_from_file_location('c',Path(__file__).with_name('build_manufacturer_seed.py'));c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
path=c.OUT/'manifest.json';m=json.loads(path.read_text(encoding='utf-8'))
for r in m['products']:
 r['category']=r.get('manufacturer_category') or c.classify(r['name'],r['source_url'],[f['title']+' '+f.get('description','') for f in r['features']])
 r['additional_categories']=[x for x in r.get('additional_categories',[]) if x not in ['CCTV Kits and Recording Systems']]
 if 'camera kit' in r['short_description'].lower() or 'security camera kit' in r['short_description'].lower():r['additional_categories'].append('CCTV Kits and Recording Systems')
 r['installation_required']=r['category'] not in ['Installation Accessories','Wi-Fi Routers and Access Points']
path.write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding='utf-8')
report_path=c.OUT/'report.json';report=json.loads(report_path.read_text(encoding='utf-8'))
report['categories']=dict(Counter(r['category'] for r in m['products']))
report['additional_categories']=dict(Counter(cat for r in m['products'] for cat in r['additional_categories']))
report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('Final categories',report['categories']);print('Additional categories',report['additional_categories'])
