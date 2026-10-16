import urllib.request
from pathlib import Path
from bs4 import BeautifulSoup
for slug in ['robots.txt','sitemap.xml','products']:
 try:
  data=urllib.request.urlopen('https://www.ezviz.com/'+slug,timeout=25).read();Path('catalogue_seed/ezviz-'+slug.replace('.','-')+'.txt').write_bytes(data)
  if slug=='products':
   s=BeautifulSoup(data,'html.parser');links=sorted({a['href'].split('?')[0] for a in s.select('a[href]') if '/product/' in a['href']});print('EZVIZ products',len(links),links[:8])
  else:print(slug,len(data),data[:700].decode(errors='replace'))
 except Exception as e:print(slug,type(e).__name__,str(e))
s=BeautifulSoup(Path('catalogue_seed/ezviz-discovery.html').read_text(encoding='utf-8'),'html.parser')
for i in s.find_all('img',alt=lambda x:x and 'Next-Generation' in x)[:8]:print('PRODUCT IMG',i.get('src'),[(p.name,p.get('class'),p.get('id')) for p in list(i.parents)[:3]])
