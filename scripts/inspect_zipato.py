import urllib.request
from bs4 import BeautifulSoup
from pathlib import Path
for suffix in ['robots.txt','shop','sitemap_index.xml']:
    try:
        data=urllib.request.urlopen('https://www.zipato.com/'+suffix,timeout=30).read()
        Path('catalogue_seed/zipato/source_html/'+suffix.replace('/','_').replace('.xml','.txt')).write_bytes(data)
        soup=BeautifulSoup(data,'html.parser')
        if suffix=='shop':
            links=sorted({a['href'] for a in soup.select('a[href]') if '/product/' in a['href']})
            print('Shop product links:',len(links));print('\n'.join(links))
        else: print(suffix,data[:1500].decode(errors='replace'))
    except Exception as exc: print(suffix,type(exc).__name__,str(exc))
