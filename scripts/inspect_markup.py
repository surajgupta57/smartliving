from pathlib import Path
from bs4 import BeautifulSoup
for file in ['tplink-product','shelly-product','sonoff-product','vigi-camera','zipato/source_html/zipatile2']:
 p=Path('catalogue_seed/'+file+('.html' if not file.endswith('.html') else ''))
 soup=BeautifulSoup(p.read_text(encoding='utf-8',errors='replace'),'html.parser')
 print('\nFILE',file)
 for selector in ['.product-image','.product-info','.product-gallery','.product-features','.overview','.product-description','.product__description','.product__media','h2','h3']:
  nodes=soup.select(selector)
  if nodes:print(selector,len(nodes),[(n.get_text(' | ',strip=True)[:220],n.get('class')) for n in nodes[:4]])
 print('IMAGES',[(im.get('src') or im.get('data-src'),im.get('alt'),im.parent.get('class')) for im in soup.select('img') if im.get('src') and ('product' in im.get('src','').lower() or file=='tplink-product')][:25])
 print('PRODUCTLINKS',[a.get('href') for a in soup.select('a[href]') if '/vigi-' in a.get('href')][-15:])
 print('JSONLD',[(x.get('type'),x.get_text()[:300]) for x in soup.select('script[type="application/ld+json"]')][:1])
