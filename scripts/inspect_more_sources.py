import urllib.request,json
from pathlib import Path
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
urls={'shelly-page2':'https://www.shelly.com/products.json?limit=250&page=2','tplink-router':'https://www.tp-link.com/in/home-networking/wifi-router/','vigi-camera':'https://www.vigi.com/in/business-networking/vigi-network-camera/','omada-switch':'https://www.omadanetworks.com/in/business-networking/omada-switch/','tplink-product':'https://www.tp-link.com/in/home-networking/wifi-router/archer-ax55/','shelly-product':'https://www.shelly.com/products/shelly-1-mini-gen4','sonoff-product':'https://sonoff.tech/products/sonoff-mini-one-matter-over-wifi-smart-switch-mini-1gs'}
def work(item):
 key,url=item
 try:
  data=urllib.request.urlopen(url,timeout=35).read();Path('catalogue_seed/'+key+'.html').write_bytes(data)
  if '.json' in url:
   p=json.loads(data)['products'];return key,len(p),[(x['title'],len(x['body_html'] or '')) for x in p[:5]]
  soup=BeautifulSoup(data.decode('utf-8',errors='replace'),'html.parser')
  links=sorted({a['href'] for a in soup.select('a[href]') if any(x in a['href'] for x in ['archer','tapo','vigi','tl-','sg2','sg3'])})
  tables=soup.select('table');
  return key,len(data),links[:8],len(links),len(tables),str(tables[0])[:2000] if tables else 'NO TABLE',soup.select_one('h1').get_text(' ',strip=True) if soup.select_one('h1') else 'NO H1'
 except Exception as exc:return key,type(exc).__name__,str(exc)
with ThreadPoolExecutor(max_workers=4) as pool:
 for r in pool.map(work,urls.items()):print(r)
