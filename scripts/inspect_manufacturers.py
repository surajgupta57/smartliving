import urllib.request, json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from bs4 import BeautifulSoup
urls={'shelly':'https://www.shelly.com/products.json?limit=250','sonoff':'https://sonoff.tech/products.json?limit=250','tplink':'https://www.tp-link.com/in/product-catalogue/','hikvision':'https://www.hikvision.com/en/products/IP-Products/Network-Cameras/','tapo':'https://www.tapo.com/en/product/'}
def get(pair):
 name,url=pair
 try:
  req=urllib.request.Request(url,headers={'User-Agent':'SmartLivingCatalogue/1.0 (+manufacturer product research)'})
  data=urllib.request.urlopen(req,timeout=35).read()
  Path('catalogue_seed/'+name).mkdir(exist_ok=True)
  Path('catalogue_seed/'+name+'/discovery.txt').write_bytes(data)
  if '.json' in url:
   products=json.loads(data).get('products',[])
   return name,len(products),[(p['title'],p['handle'],p.get('product_type')) for p in products[:8]]
  soup=BeautifulSoup(data,'html.parser')
  links=sorted({a['href'] for a in soup.select('a[href]') if any(x in a['href'].lower() for x in ['/home-networking/','/business-networking/','/network-cameras/','/product/'])})
  return name,len(data),len(links),links[:12]
 except Exception as exc:return name,type(exc).__name__,str(exc)
with ThreadPoolExecutor(max_workers=4) as pool:
 for item in pool.map(get,urls.items()): print(item)
