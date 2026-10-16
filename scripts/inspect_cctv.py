import urllib.request
from pathlib import Path
from bs4 import BeautifulSoup
for label,url in [('cpplus','https://www.cpplusworld.com/products/network-camera'),('ezviz','https://www.ezviz.com/product/C6N-G1-2K/293591')]:
 try:
  data=urllib.request.urlopen(url,timeout=25).read();Path('catalogue_seed/'+label+'-discovery.html').write_bytes(data)
  s=BeautifulSoup(data.decode('utf-8',errors='replace'),'html.parser')
  links=sorted({a['href'] for a in s.select('a[href]') if '/products/' in a['href']})
  print(label,len(data),links[:35])
  print('spec tables',len(s.select('table')),'img paths',[(i.get('src'),i.get('alt')) for i in s.select('img') if 'product' in (i.get('src') or '').lower()][:8])
 except Exception as e:print(label,type(e).__name__,str(e))
