from pathlib import Path
from bs4 import BeautifulSoup
for file in ['sonoff-product','shelly-product','tplink-product','zipato/source_html/zipatile2']:
 s=BeautifulSoup(Path('catalogue_seed/'+file+'.html').read_text(encoding='utf-8',errors='replace'),'html.parser')
 print('\n',file)
 for n in s.find_all(string=lambda x:x and any(k in x.strip().lower() for k in ['specification','rated current','input voltage','device model','model name'])):
  if n.parent.name not in ['script','style']:
   print(str(n)[:90],[(p.name,p.get('class'),p.get('id')) for p in list(n.parents)[:3]])
 print('first PRODUCT imagery',[(i.get('src') or i.get('data-src'), i.get('alt'),i.parent.name,i.parent.get('class')) for i in s.select('.images img,.product-gallery img,.product__media img,.product-image img')][:10])
 if file=='sonoff-product':
  print('spec classes',sorted({str(n.get('class')) for n in s.select('[class]') if 'spec' in ' '.join(n.get('class',[]))})[:30])
 if file=='tplink-product':
  for n in s.find_all('h1'): print('h1 parents',[(p.name,p.get('class')) for p in list(n.parents)[:3]])
  print('summary list',[(ul.get('class'),ul.get_text(' | ',strip=True)[:350]) for ul in s.select('ul') if 'AX3000' in ul.get_text()][:5])
