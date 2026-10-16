import json,urllib.request,concurrent.futures
from pathlib import Path
from urllib.parse import urljoin,urlsplit
from bs4 import BeautifulSoup
base=BeautifulSoup(Path('catalogue_seed/tplink/discovery.txt').read_text(encoding='utf-8'),'html.parser')
urls=set()
for a in base.select('a[href]'):
 u=urljoin('https://www.tp-link.com',a['href']).split('?')[0].split('#')[0]
 p=urlsplit(u)
 if p.hostname in ['www.tp-link.com','www.vigi.com','www.omadanetworks.com'] and '/in/' in p.path and any(x in p.path for x in ['home-networking/','smart-home/','business-networking/']) and len(p.path.strip('/').split('/')) in [3,4] and not any(x in p.path for x in ['case-study','solution','technology','robot-vacuum','software-service','solar-power','all-omada-pro','all-pharos','service-provider']):urls.add(u)
urls.add('https://www.omadanetworks.com/in/business-networking/all-omada-switch/')
urls.add('https://www.omadanetworks.com/in/business-networking/all-omada-wifi/')
urls.add('https://www.omadanetworks.com/in/business-networking/all-omada-router/')
found=set()
def get(u):
 try:
  req=urllib.request.Request(u,headers={'User-Agent':'SmartLivingCatalogue/1.0'})
  data=urllib.request.urlopen(req,timeout=30).read();s=BeautifulSoup(data.decode('utf-8',errors='replace'),'html.parser')
  links=set()
  for a in s.select('a[href]'):
   link=urljoin(u,a['href']).split('?')[0].split('#')[0];p=urlsplit(link)
   if p.hostname in ['www.tp-link.com','www.vigi.com','www.omadanetworks.com'] and len(p.path.strip('/').split('/'))==4 and '/in/' in p.path and any(x in p.path for x in ['home-networking/','business-networking/','smart-home/']):links.add(link)
  return u,links
 except Exception as exc:return u,set()
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
 for u,links in pool.map(get,sorted(urls)):
  found.update(links)
  print(u,len(links),flush=True)
Path('catalogue_seed/tplink_candidates.json').write_text(json.dumps(sorted(found),indent=2),encoding='utf-8')
print('TOTAL CANDIDATES',len(found),flush=True)
