import importlib.util,json,concurrent.futures,xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlsplit,urljoin
spec=importlib.util.spec_from_file_location('collector',Path('scripts/build_manufacturer_seed.py'));c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
root=ET.fromstring(Path('catalogue_seed/ezviz-sitemap-xml.txt').read_bytes())
urls=sorted({n.text for n in root.findall('.//loc') if n.text and urlsplit(n.text).path.startswith('/product/') and not any(w in n.text.lower() for w in ['robot','vacuum','clean','rs2','rs20','re4','re5','rh1','rh2','rh3','eb3-adaptor'])})
print('EZVIZ global product URLs',len(urls),flush=True)
def parse(url):
 try:
  s=c.soup_url(url)
  specs=c.specs_from_tables(s)
  model=next((r['value'] for r in specs if r['name'].lower()=='model'),'')
  title=c.text(s.select_one('title')).split(' - EZVIZ')[0]
  if not model or len(specs)<5:return None
  name=title.split('—')[0].split(' – ')[0].strip()
  if name=='EZVIZ - Creating Easy Smart Homes':
   hero=s.select_one('.pro-img img')
   name=(hero.get('alt') if hero else '') or model
  if any(x in name.lower() for x in ['robot','vacuum','cleaner']):return None
  imgs=[]
  for i in s.select('.pro-img img, .pwhole img, img'):
   alt=i.get('alt','');src=i.get('src') or i.get('data-src') or ''
   if ('ezviz' in alt.lower() and len(alt)>15 or i.find_parent(class_='pro-img') or i.find_parent(class_='pwhole')) and 'mfs.ezvizlife.com' in src:imgs.append(urljoin(url,src))
  hero=s.select_one('.pro-img img')
  if hero and hero.get('src'):imgs=[urljoin(url,hero['src'])]+imgs
  if len(set(imgs))<2:return None
  short=title.split('—',1)[-1].strip() if '—' in title else name
  feature_values=[]
  for r in specs:
   if r['name'].lower() in ['max. resolution','video compression','smart alarm','lens','ir range','resolution','wifi','wi-fi','network','storage']:
    feature_values.append(r['name']+': '+r['value'])
  r=c.finish('EZVIZ','EZVIZ '+name,model,url,short,feature_values,specs,imgs)
  return r
 except Exception:return None
records=[];seen=set()
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
 for index,r in enumerate(pool.map(parse,urls[:200]),1):
  if r and r['key'] not in seen:records.append(r);seen.add(r['key'])
  if index%20==0:print('EZVIZ pages',index,'qualified',len(records),flush=True)
c.OUT.joinpath('ezviz_records.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
print('EZVIZ qualified',len(records),flush=True)


