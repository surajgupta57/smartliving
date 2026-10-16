from pathlib import Path
from bs4 import BeautifulSoup
s=BeautifulSoup(Path('catalogue_seed/cpplus-discovery.html').read_text(encoding='utf-8'),'html.parser')
i=s.find('img',alt='CP-UNC-EE61L2C-VMD-Q')
print('CP LINK',str(i.find_parent('a'))[:2200]);print('paginated links',[(a.get('href'),a.get_text()) for a in s.select('a[href]') if '?page' in a['href']])
s=BeautifulSoup(Path('catalogue_seed/ezviz-discovery.html').read_text(encoding='utf-8'),'html.parser')
print('EZ TABLE',str(s.select_one('table'))[:2600]);print('EZ PRODUCT LIST LINKS',[(a.get('href'),a.get_text()[:50]) for a in s.select('a[href]') if '/product/' in a['href']][:12]);print('EZ IMG',[(i.get('src') or i.get('data-src'),i.get('alt')) for i in s.select('img')][-20:])
