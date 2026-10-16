import importlib.util,json
from pathlib import Path
spec=importlib.util.spec_from_file_location('c',Path('scripts/build_manufacturer_seed.py'));c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
s=c.soup_url('https://www.zipato.com/product/zipabox2');tab=s.select_one('#tab-description') or s
print('HEADINGS',[(n.name,c.text(n)) for n in tab.select('h2,h3,h4,strong')][:35])
print('FULL',c.text(tab)[:11000])
print('DOCS',[(a.get('href'),c.text(a)) for a in tab.select('a[href]') if '.pdf' in a['href']])
