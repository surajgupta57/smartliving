from pathlib import Path
from bs4 import BeautifulSoup
s=BeautifulSoup(Path('catalogue_seed/sonoff-product.html').read_text(encoding='utf-8'),'html.parser')
n=s.select_one('.shopify-section--specification-table')
print(str(n)[:6500])
s=BeautifulSoup(Path('catalogue_seed/tplink-product.html').read_text(encoding='utf-8'),'html.parser')
print('BRIEF',str(s.select_one('.brief'))[:3400]);print('GALLERY LINKS',[(a.get('href'),a.get('data-img'),a.get('data-src')) for a in s.select('a[href]') if 'image-line' in a.get('href','')][:15])
s=BeautifulSoup(Path('catalogue_seed/zipato/source_html/zipatile2.html').read_text(encoding='utf-8'),'html.parser')
head=s.find('h2',string=lambda x:x and 'TECHNICAL' in x)
print('ZIP SPEC',str(head.parent)[:4500]);print('ZIP IMGS',[(a.get('href'),a.get('class')) for a in s.select('a[href]') if any(x in a.get('href','').lower() for x in ['.png','.jpg','.jpeg','.pdf'])][:12])
