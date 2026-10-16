import importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('c',Path('scripts/build_manufacturer_seed.py'));c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
s=c.soup_url('https://www.ezviz.com/product/A3-Home-Gateway/40264')
print([(i.get('src') or i.get('data-src'),i.get('alt'),i.parent.get('class')) for i in s.select('img')][-25:]);print('H1',[(c.text(h),h.get('class')) for h in s.select('h1,h2')][:15]);print('CSS IMAGES',[line[:170] for line in str(s).splitlines() if 'background-image' in line][:10])
