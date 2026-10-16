import urllib.request
from bs4 import BeautifulSoup
from pathlib import Path
base='https://www.zipato.com/'
for slug in ['zipatile2','micro-module-switch-double','ip-camera']:
 data=urllib.request.urlopen(base+'product/'+slug,timeout=30).read()
 Path('catalogue_seed/zipato/source_html/'+slug+'.html').write_bytes(data)
 soup=BeautifulSoup(data,'html.parser')
 print('\nPRODUCT',slug)
 for selector in ['h1','.summary','.woocommerce-product-gallery','#tab-description','#tab-additional_information','.woocommerce-tabs']:
  n=soup.select_one(selector)
  print(selector, (str(n)[:1800] if selector=='.woocommerce-product-gallery' else n.get_text(' | ',strip=True)[:6500]) if n else 'NONE')

