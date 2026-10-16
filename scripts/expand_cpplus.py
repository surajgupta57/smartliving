"""Capture a focused India catalogue of analog CCTV and installation equipment."""
import importlib.util,concurrent.futures,json
from pathlib import Path
from urllib.parse import urljoin
spec=importlib.util.spec_from_file_location('collector',Path(__file__).with_name('build_manufacturer_seed.py'));c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
categories={'analog-hd-camera':'HD Analog CCTV Cameras','accessories':'CCTV Accessories','vdp':'Video Door Phones and Smart Doorbells','time-attendance':'Smart Locks and Access Control','network-camera':'CCTV IP Cameras','nvr':'NVR and DVR Recorders','dvr':'NVR and DVR Recorders'}
tasks=[];seen=set()
for slug,category in categories.items():
 try:
  s=c.soup_url('https://www.cpplusworld.com/products/'+slug)
  links=[urljoin('https://www.cpplusworld.com',a['href']) for a in s.select('a.item-image[href]')]
  for u in links[:12 if slug=='analog-hd-camera' else 8]:
   if u not in seen:tasks.append((u,category));seen.add(u)
 except Exception as exc:print(slug,str(exc),flush=True)
print('CP PLUS candidates',len(tasks),flush=True)
def process(task):
 u,category=task
 try:
  s=c.soup_url(u);model=c.text(s.select_one('h1.product-title'))
  if not model:return None
  rows=c.specs_from_tables(s);features=[c.text(li) for li in s.select('.product-info-list li')]
  imgs=[urljoin(u,a['href']) for a in s.select('.product-thumbnail-list a[href]') if '/prodassets/product/' in a['href']]
  if not imgs:imgs=[urljoin(u,i['src']) for i in s.select('.product-thumbnail-list img[src]')]
  if len(rows)<4 or len(imgs)<2:return None
  docs=[{'title':'CP PLUS '+model+' datasheet','url':urljoin(u,a['href'])} for a in s.select('a[href]') if '/prodassets/datasheet/' in a['href']][:1]
  r=c.finish('CP PLUS','CP PLUS '+model,model,u,'; '.join(features[:2]),features,rows,imgs,docs)
  r['manufacturer_category']=category
  r['category']=category
  return r
 except Exception:return None
ready=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
 for index,r in enumerate(pool.map(process,tasks),1):
  if r:ready.append(r)
  if index%10==0:print('CP PLUS pages',index,'qualified',len(ready),flush=True)
c.OUT.joinpath('cpplus_records.json').write_text(json.dumps(ready,ensure_ascii=False,indent=2),encoding='utf-8')
print('CP PLUS qualified',len(ready),flush=True)
