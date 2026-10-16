import importlib.util, json, concurrent.futures
from pathlib import Path
spec=importlib.util.spec_from_file_location('collector',Path('scripts/build_manufacturer_seed.py'));c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
items=c.shopify_candidates('Shelly',400)
old=json.loads(c.OUT.joinpath('records.json').read_text(encoding='utf-8'))
seen={r['source_url'] for r in old}
items=[i for i in items if 'https://www.shelly.com/products/'+i[1]['handle'] not in seen]
print('Additional Shelly candidates',len(items),flush=True)
records=[]
def process(item):
 try:
  r=c.parse_shopify(item)
  if len(r['specifications'])>=4 and len(r['source_images'])>=2:return r
 except Exception:pass
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
 for index,r in enumerate(pool.map(process,items),1):
  if r:records.append(r)
  if index%20==0:print('Extra pages',index,'qualified',len(records),flush=True)
c.OUT.joinpath('extra_records.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
print('Extra qualified',len(records),flush=True)
