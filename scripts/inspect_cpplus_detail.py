import urllib.request
from pathlib import Path
from bs4 import BeautifulSoup
for slug in ['cp-unc-ee61l2c-vmd-q','products/analog-hd-camera','products/accessories']:
 try:
  u='https://www.cpplusworld.com/'+slug;data=urllib.request.urlopen(u,timeout=25).read();s=BeautifulSoup(data.decode('utf-8',errors='replace'),'html.parser')
  Path('catalogue_seed/cp-'+slug.replace('/','-')+'.html').write_bytes(data)
  print(slug,'tables',len(s.select('table')),'models',[(a.get('href'),a.get_text(' ',strip=True)[:40]) for a in s.select('a.item-image')][:5])
  print('imgs',[(i.get('src'),i.get('alt'),i.parent.get('class')) for i in s.select('img') if '/prodassets/product/' in (i.get('src') or '')][:8])
  if s.select('table'):print('spec text',s.select_one('table').get_text(' | ',strip=True)[:600])
 except Exception as e:print(type(e).__name__,str(e))
