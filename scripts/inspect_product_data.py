import json,urllib.request
from bs4 import BeautifulSoup
from pathlib import Path
for name in ['shelly','sonoff']:
 products=json.loads(Path('catalogue_seed/'+name+'/discovery.txt').read_text(encoding="utf-8"))['products']
 print(name, 'all titles',[(p['title'],len(p['images'])) for p in products if not any(x in p['title'].lower() for x in ['pack','bundle','course','gift','t-shirt'])][:25])
 p=next(p for p in products if ('1 mini gen4' in p['title'].lower() if name=='shelly' else 'minir4' in p['title'].lower()))
 print('EXAMPLE',p['title'],p['tags'],p['variants'][:1])
 soup=BeautifulSoup(p['body_html'],'html.parser')
 print('TEXT',soup.get_text(' | ',strip=True)[:6000]); print('TABLES',str(soup.select('table'))[:4500])
soup=BeautifulSoup(Path('catalogue_seed/tplink/discovery.txt').read_bytes(),'html.parser')
print('TP-LINK product paths',sorted({a['href'] for a in soup.select('a[href]') if '/in/' in a['href']})[-80:])

