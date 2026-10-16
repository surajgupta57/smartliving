import importlib.util,xml.etree.ElementTree as ET
from pathlib import Path
spec=importlib.util.spec_from_file_location('c',Path('scripts/build_manufacturer_seed.py'));c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
root=ET.fromstring(Path('catalogue_seed/ezviz-sitemap-xml.txt').read_bytes())
urls=sorted({n.text for n in root.findall('.//loc') if n.text and '/product/' in n.text and '/product/'==n.text[n.text.find('.com')+4:n.text.find('.com')+13]})
print(urls[:5])
for u in urls[:2]+['https://www.ezviz.com/product/C6N-G1-2K/293591']:
 try:
  s=c.soup_url(u);rows=c.specs_from_tables(s)
  print(u,c.text(s.select_one('title')),len(rows),rows[:2],[(i.get('src'),i.get('alt')) for i in s.select('img') if 'ezviz' in (i.get('alt') or '').lower()][:2])
 except Exception as e:print(type(e).__name__,str(e))
