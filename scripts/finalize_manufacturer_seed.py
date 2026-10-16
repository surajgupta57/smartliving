"""Finalize the audited 500-product offline bundle, resuming per-product media work."""
import concurrent.futures,importlib.util,json,re,hashlib,io
from collections import Counter,defaultdict
from pathlib import Path
from datetime import datetime,timezone
from PIL import Image
spec=importlib.util.spec_from_file_location('collector',Path(__file__).with_name('build_manufacturer_seed.py'));c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
checkpoint=c.OUT/'enriched';checkpoint.mkdir(exist_ok=True)
records=[];seen=set()
for filename in ['records.json','extra_records.json','ezviz_records.json','cpplus_records.json']:
 for r in json.loads((c.OUT/filename).read_text(encoding='utf-8')):
  if r['key'] in seen:continue
  if re.search(r'\bx[2-9]\b|\b[2-9]\s*x\b',r['name'],re.I):continue
  seen.add(r['key'])
  features=r['features']
  if r['brand']=='SONOFF' and features:
   whole=' '.join(f.get('description') or f['title'] for f in features)
   pieces=re.split(r'【([^】]+)】',whole)
   if len(pieces)>2:features=[{'title':c.clean(pieces[i])[:120],'description':c.clean(pieces[i+1])} for i in range(1,len(pieces)-1,2) if c.clean(pieces[i])][:10]
  r['features']=features
  r['category']=r.get('manufacturer_category') or c.classify(r['name'],r['source_url'],[f['title']+' '+f.get('description','') for f in features])
  hay=(r['short_description']+' '+' '.join(f['title'] for f in features)).lower()
  r['additional_categories']=[]
  if r['category'] in ['CCTV IP Cameras','Wi-Fi and 4G Cameras','PTZ Cameras']:
   if 'dome' in hay or 'turret' in hay:r['additional_categories'].append('Dome and Turret Cameras')
   if 'bullet' in hay:r['additional_categories'].append('Bullet Cameras')
  r['full_description']=r['short_description']+'\n\n'+r['name']+' is listed in the '+r['brand']+' manufacturer catalogue. Review the technical specifications and gallery for its published configuration.\n\nRequest a quotation to confirm the regional variant, hardware revision, compatibility, installation scope and local availability.'
  records.append(r)
groups=defaultdict(list)
for r in records:groups[(r['brand'],r['category'])].append(r)
queue=[]
while any(groups.values()):
 for key in sorted(groups):
  if groups[key]:queue.append(groups[key].pop(0))
print('Audited source candidates',len(queue),dict(Counter(r['brand'] for r in queue)),flush=True)

def perceptual(path):
 with Image.open(path) as im:
  pixels=list(im.convert('L').resize((9,8)).getdata())
 return sum((1<<i) for i in range(64) if pixels[(i//8)*9+(i%8)]>pixels[(i//8)*9+(i%8)+1])

def enrich(r):
 path=checkpoint/(c.digest(r['key'])+'.json')
 if path.exists():
  old=json.loads(path.read_text(encoding='utf-8'))
  r['images']=old.get('images',[]);r['documents']=old.get('documents',[])
  return r
 r=c.enrich(r)
 # Remove exact-view duplicates (for example thumbnail/full-size versions).
 filtered=[];hashes=[]
 for image in r['images']:
  h=perceptual(c.OUT/image['path'])
  if any((h^previous).bit_count()<=2 for previous in hashes):continue
  hashes.append(h);filtered.append(image)
 r['images']=filtered
 if len(r['images'])<2:
  r['media_quality']='Insufficient distinct gallery views'
 path.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
 return r

ready=[];processed=0
with concurrent.futures.ThreadPoolExecutor(max_workers=7) as pool:
 futures={pool.submit(enrich,r):r for r in queue}
 for future in concurrent.futures.as_completed(futures):
  processed+=1
  try:
   r=future.result()
   if len(r['images'])>=2:ready.append(r)
  except Exception as exc:c.errors.append({'url':futures[future]['source_url'],'reason':str(exc),'type':'quality'})
  if processed%25==0:print('Gallery checked',processed,'/',len(queue),'complete',len(ready),flush=True)
  # Finish already-running requests but stop scheduling work once enough qualified products exist.
  if len(ready)>=500:
   for f in futures:
    if not f.done():f.cancel()
   break
# Use deterministic discovery order rather than completion order.
order={r['key']:i for i,r in enumerate(queue)}
ready=sorted(ready,key=lambda r:order[r['key']])[:500]
for r in ready:r['is_featured']=False
for brand in sorted({r['brand'] for r in ready}):
 choices=[r for r in ready if r['brand']==brand]
 choices.sort(key=lambda r:(not any(k in r['name'].lower() for k in ['gen4','mini one','ax55','c6n','zipatile2','tapo c']),r['name']))
 for r in choices[:2]:r['is_featured']=True
manifest={'schema_version':1,'generated_at':datetime.now(timezone.utc).isoformat(),'requested_count':500,'product_count':len(ready),'selection':'Official manufacturer records. No invented reviews, ratings, prices or stock. Minimum two distinct downloaded images and four published specification rows.','products':ready}
c.OUT.joinpath('manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
report={'requested':500,'ready':len(ready),'qualified_candidates':len(queue),'brands':dict(Counter(r['brand'] for r in ready)),'categories':dict(Counter(r['category'] for r in ready)),'additional_categories':dict(Counter(cat for r in ready for cat in r['additional_categories'])),'images':sum(len(r['images']) for r in ready),'specifications':sum(len(r['specifications']) for r in ready),'features':sum(len(r['features']) for r in ready),'documents':sum(len(r['documents']) for r in ready),'minimum_gallery':min((len(r['images']) for r in ready),default=0),'minimum_specifications':min((len(r['specifications']) for r in ready),default=0),'errors':c.errors}
c.OUT.joinpath('report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('FINAL',json.dumps({k:v for k,v in report.items() if k!='errors'}),flush=True)
if len(ready)!=500:raise SystemExit('Need more source-qualified products; bundle is not complete.')
