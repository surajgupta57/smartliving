"""Build a factual, portable catalogue from public official manufacturer pages.
Caches source responses, respects robots rules, and never generates product data.
Usage: python scripts/build_manufacturer_seed.py --target 500
"""
import argparse, concurrent.futures, gzip, hashlib, io, json, re, threading, time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urldefrag, quote
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser
from bs4 import BeautifulSoup
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'catalogue_seed' / 'manufacturers'
CACHE = OUT / 'cache'
AGENT = 'SmartLivingCatalogue/1.0'
ALLOWED = {'www.zipato.com','zipato.com','www.shelly.com','sonoff.tech','www.tp-link.com','www.vigi.com','www.omadanetworks.com','static.tp-link.com','static-product.tp-link.com','cdn.shopify.com','sonoff.tech','shelly.com','www.ezviz.com','ezviz.com','mfs.ezvizlife.com','statics.ezvizlife.com','www.cpplusworld.com','cpplusworld.com'}
_lock = threading.Lock(); _last = {}; _robots = {}; errors = []

def clean(value):
    return re.sub(r'\s+', ' ', str(value or '')).strip()

def text(node):
    return clean(node.get_text(' ', strip=True)) if node else ''

def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()

def fetch(url):
    url = quote(url, safe=':/?=&%+@,')
    host = urlsplit(url).hostname
    if host not in ALLOWED: raise ValueError('Unapproved source host: '+str(host))
    path = CACHE / (digest(url)+'.gz')
    if path.exists(): return gzip.decompress(path.read_bytes())
    for attempt in range(3):
        with _lock:
            delay = max(0, .35 - (time.monotonic()-_last.get(host, 0)))
            if delay: time.sleep(delay)
            _last[host] = time.monotonic()
        try:
            req = Request(url, headers={'User-Agent':AGENT, 'Accept-Encoding':'identity'})
            with urlopen(req, timeout=35) as response:
                if urlsplit(response.url).hostname not in ALLOWED: raise ValueError('Unexpected redirect host')
                data = response.read(16*1024*1024+1)
            if len(data)>16*1024*1024: raise ValueError('Source file exceeds 16 MB')
            path.write_bytes(gzip.compress(data))
            return data
        except Exception:
            if attempt == 2: raise
            time.sleep(1+attempt)

def allowed_page(url):
    host = urlsplit(url).hostname
    if host not in _robots:
        parser = RobotFileParser()
        try:
            parser.parse(fetch(f'https://{host}/robots.txt').decode('utf-8',errors='replace').splitlines())
            _robots[host] = parser
        except Exception:
            _robots[host] = None
    parser = _robots[host]
    return parser is None or parser.can_fetch(AGENT, url)

def soup_url(url):
    if not allowed_page(url): raise ValueError('robots.txt disallows source URL')
    return BeautifulSoup(fetch(url).decode('utf-8',errors='replace'),'html.parser')

def specs_from_tables(soup):
    rows=[]
    for table in soup.select('table'):
        group=text(table.select_one('thead'))[:80] or 'Technical specifications'
        for row in table.select('tr'):
            cells=row.find_all(['td','th'],recursive=False)
            if len(cells)==1 and cells[0].get('colspan'): group=text(cells[0])[:80];continue
            if len(cells)!=2:continue
            name,value=text(cells[0]).strip(' :'),text(cells[1])
            if not name or not value or name.lower() in ['quantity','heading','attribute','specification']:continue
            rows.append({'name':name[:100], 'value':value, 'group':group})
    return rows

def unique_specs(rows):
    result=[];seen=set()
    for row in rows:
        key=(row['name'],row['value'])
        if key not in seen and len(row['value'])<10000:
            seen.add(key);result.append(row)
    return result

def classify(name,url,features):
    raw=(name+' '+url).lower(); n=raw+' '+raw.replace('-', ' '); f=' '.join(features).lower()
    if any(w in n for w in ['recorder','nvr','dvr']):return 'NVR and DVR Recorders'
    if any(w in n for w in ['doorbell','door phone','intercom']):return 'Video Door Phones and Smart Doorbells'
    if any(w in n for w in ['camera','tapo-c','tapo-tc','vigi-c']):
        if any(w in n+f for w in ['pan/tilt','pan-tilt','ptz','pan tilt']):return 'PTZ Cameras'
        if any(w in n+f for w in ['wi-fi','wifi','wireless','4g','lte']):return 'Wi-Fi and 4G Cameras'
        return 'CCTV IP Cameras'
    if any(w in n for w in ['rfid','keypad','smart lock','fingerprint lock','door lock','loqed']):return 'Smart Locks and Access Control'
    if 'motor controller' in n or re.search(r'\b(curtains?|roller|shutters?)\b',n):return 'Smart Curtains and Blinds'
    if any(w in n for w in ['trv','thermostat','ac controller','ir controller','zxt600','shelly h&t']):return 'Climate and Appliance Control'
    if any(w in n for w in ['sensor','siren','alarm','multisensor','leak','valve controller','motion']):return 'Intrusion Alarms and Smart Sensors'
    if any(w in n for w in ['deco','archer','router','access-point','range-extender','omada-wifi','eap','cpe','wireless-bridge']):return 'Wi-Fi Routers and Access Points'
    if '/business-networking/' in n and 'switch' in n:return 'Networking and PoE Switches'
    if any(w in n for w in ['network-switch','soho-switch','omada-switch','managed-switch','unmanaged-switch','sg2','sg3','sg1','tl-sg','tl-sf']):return 'Networking and PoE Switches'
    if 'vigi-accessory' in n:return 'CCTV Accessories'
    if any(w in n for w in ['adapter','cable','accessor','mount','enclosure','waterproof box','din rail holder','frame','bracket','addon','add-on','transformer','clamp','shelly pro dual cover']):return 'Installation Accessories'
    if any(w in n for w in ['bulb','rgb','dimmer','wall switch','switchman','micro module switch','smart-switch','plug','shelly 1','shelly 2','shelly plus 1','shelly plus 2','shelly pro 1','shelly pro 2','shelly pro 3','shelly pro 4','shelly wave 1','shelly wave 2','shelly wave pro','mini-','minir','basic','pow','4ch','dualr','zbmini']):return 'Smart Switches and Lighting'
    return 'Smart Home Automation'

def finish(brand,name,model,url,short,features,specs,images,documents=None):
    features=list(dict.fromkeys(clean(x) for x in features if clean(x)))[:10]
    specs=unique_specs(specs)
    model=clean(model)[:100]
    name=clean(name)[:180]
    key=brand.lower()+':'+re.sub(r'[^a-z0-9]','',model.lower() or name.lower())
    specs=unique_specs([{'name':'Model','value':model,'group':'Identity'}] + specs) if model else specs
    category=classify(name,url,features)
    intro=clean(short)[:280] or f'{name}. Manufacturer-listed {category.lower()} equipment; review the technical specifications for the selected configuration.'
    # Original concise overview; published engineering facts remain in structured fields.
    overview=f'{name} is listed by {brand} in its manufacturer catalogue. '
    overview+=f'This product is classified under {category.lower()}. '
    overview+='Review the manufacturer specifications and available gallery views below when comparing the system for your property. '
    overview+='Request a quotation to confirm the supplied regional variant, compatibility, installation scope and availability.'
    protocols=[]
    hay=' '.join([name,short]+features+[x['value'] for x in specs])
    for protocol in ['Matter','Zigbee','Z-Wave','Bluetooth','Wi-Fi','ONVIF','PoE','Ethernet']:
        if protocol.lower() in hay.lower():protocols.append(protocol)
    return {'key':key,'sku':'SL-'+brand.upper().replace(' ','-')[:14]+'-'+digest(key)[:12].upper(),'brand':brand,'name':name,'model_number':model,'category':category,'additional_categories':[],'source_url':url,'source_checked_at':datetime.now(timezone.utc).isoformat(),'short_description':intro,'full_description':overview,'features':[{'title':f.split('—')[0].split(' - ')[0][:120], 'description':f if len(f)>120 else ''} for f in features],'specifications':specs,'source_images':list(dict.fromkeys(images))[:5],'source_documents':documents or [],'compatibility_information':('Manufacturer lists: '+', '.join(protocols)+'. ' if protocols else '')+'Confirm hub, protocol, regional frequency, voltage and hardware revision before ordering.','warranty_information':'Warranty terms and local service eligibility will be confirmed with your quotation.','installation_required':category not in ['Installation Accessories','Wi-Fi Routers and Access Points'],'availability_label':'Confirm regional variant and availability','is_featured':False}

def parse_tp(url):
    soup=soup_url(url)
    brief=soup.select_one('.brief')
    model=text(soup.select_one('.product-name'))
    heading=text(brief.select_one('h1') if brief else soup.select_one('h1'))
    if not model or not heading:raise ValueError('Not a product detail page')
    if soup.find(string=lambda x:x and ('End of Life' in x or x.strip()=='EOL')):raise ValueError('End-of-life product')
    specs=specs_from_tables(soup)
    features=[text(li) for li in soup.select('.brief .highlights li')]
    if not features:features=[text(li) for li in soup.select('.highlights li')][:10]
    images=[urljoin(url,a['href']) for a in soup.select('a[href]') if '/image-line/' in a['href'] and re.search(r'\.(png|jpe?g|webp)(?:\?|$)',a['href'],re.I)]
    if not images:images=[urljoin(url,i.get('src') or i.get('data-src')) for i in soup.select('img') if '/image-line/' in (i.get('src') or i.get('data-src') or '')]
    documents=[{'title':text(a)[:160] or 'Manufacturer datasheet','url':urljoin(url,a['href'])} for a in soup.select('a[href]') if re.search(r'\.pdf(?:\?|$)',a['href'],re.I) and any(x in (a['href']+' '+text(a)).lower() for x in ['datasheet','data-sheet','data_sheet','user guide','user_guide','user-guide'])][:2]
    return finish('TP-Link','TP-Link '+model,model,url,heading,features,specs,images,documents)

def parse_shopify(item):
    brand,p=item
    base='https://sonoff.tech' if brand=='SONOFF' else 'https://www.shelly.com'
    url=base+'/products/'+p['handle']
    soup=soup_url(url)
    body=BeautifulSoup(p.get('body_html') or '', 'html.parser')
    model=p['title'].split('|')[-1].strip() if '|' in p['title'] else p['title']
    specs=specs_from_tables(soup.select_one('.kb-doc') or soup.select_one('.product__info-container') or soup)
    for row in soup.select('.feature-chart__table-row'):
        n=text(row.select_one('.feature-chart__heading'));v=text(row.select_one('.feature-chart__value'))
        if n and v and n.lower() not in ['heading','value']:specs.append({'name':n[:100],'value':v,'group':'Technical specifications'})
    description=text(soup.select_one('.product-description')) or text(body)
    features=[text(li) for li in body.select('li')]
    if not features:features=[text(n) for n in body.select('p') if text(n)][:8]
    if brand=='Shelly':
        kb=soup.select_one('.kb-doc')
        if kb:
            h=kb.find('h2',string=lambda x:x and 'Main features' in x)
            if h:
                ul=h.find_next('ul');features=[text(n) for n in ul.select('li')][:10] if ul else features
            for n in kb.select('li'):
                value=text(n)
                if value.startswith(('Device model:','Device name:')):
                    specs.append({'name':value.split(':',1)[0], 'value':value.split(':',1)[1].strip(),'group':'Identity'})
                    if value.startswith('Device model:'):model=value.split(':',1)[1].strip()
    if not features:
        features=[text(n) for n in soup.select('.product-info .prose li')][:8]
    variants=p.get('variants',[])
    if variants and variants[0].get('sku'):specs.append({'name':'Manufacturer SKU','value':variants[0]['sku'],'group':'Identity'})
    docs=[{'title':text(a)[:160] or 'Manufacturer manual','url':urljoin(url,a['href'])} for a in soup.select('.shopify-section--specification-table a[href], .kb-doc a[href]') if re.search(r'\.pdf(?:\?|$)',a['href'],re.I)][:2]
    return finish(brand,p['title'],model,url,description,features,specs,[i['src'] for i in p.get('images',[])],docs)

def parse_zipato(url):
    soup=soup_url(url)
    name=text(soup.select_one('.summary .product_title')) or text(soup.select_one('.summary h1'))
    if not name:raise ValueError('Missing Zipato title')
    if 'credits' in name.lower():raise ValueError('Service credits are not a physical product')
    model=text(soup.select_one('.sku'))
    if model in ['N/A','']:model=name
    short=text(soup.select_one('.woocommerce-product-details__short-description')) or text(soup.select_one('.summary .description'))
    tab=soup.select_one('#tab-description') or soup
    specs=specs_from_tables(tab)
    # Zipato uses heading + paragraph groups rather than HTML specification tables.
    head=tab.find(['h2','h3'],string=lambda x:x and 'TECHNICAL SPEC' in x.upper())
    if head:
        group='Technical specifications'; grouped={}
        headings={'SYSTEM','POWER','SENSORS','NETWORK','INPUT/OUTPUT','ACCESSORIES','PHYSICAL DIMENSION','ENVIRONMENTAL','REGULATION','OPERATING CONDITIONS','OPERATING CONDITIONS:','OPERATION SYSTEM','IMAGE PERFORMANCE','SENSOR','ENVIRONMENT PARAMETERS','ADDITIONAL FEATURES','WARRANTY'}
        for node in head.find_all_next(['h2','h3','h4','p','li']):
            if node.name in ['h2','h3'] and any(k in text(node).upper() for k in ['GALLERY','FAQ','DOWNLOAD','FEATURES']):break
            value=text(node)
            if not value:continue
            if value.upper() in headings:group=value.strip(':').title();continue
            if len(value)<1500:grouped.setdefault(group,[]).append(value)
        specs += [{'name':group,'value':'\n'.join(dict.fromkeys(values)),'group':'Manufacturer technical data'} for group,values in grouped.items()]
    specs+=specs_from_tables(soup.select_one('#tab-additional_information') or BeautifulSoup('','html.parser'))
    features=[]
    head=tab.find(['h2','h3'],string=lambda x:x and x.strip().upper()=='FEATURES')
    if head:
        for node in head.find_all_next(['h2','h3','p','li']):
            if node.name in ['h2','h3']:break
            if 5<len(text(node))<350:features.append(text(node))
    imgs=[a['href'] for a in soup.select('a[href]') if a.get('class') and any(k in a.get('class',[]) for k in ['woocommerce-main-image','prettyphoto']) and re.search(r'\.(png|jpe?g|webp)(?:\?|$)',a['href'],re.I)]
    docs=[{'title':text(a)[:160] or 'Manufacturer document','url':a['href']} for a in tab.select('a[href]') if '.pdf' in a['href'].lower()][:2]
    return finish('Zipato','Zipato '+name,model,url,short,features,specs,imgs,docs)

def shopify_candidates(brand, maximum=120):
    host='sonoff.tech' if brand=='SONOFF' else 'www.shelly.com'
    result=[];seen=set()
    for page in range(1,7):
        url=f'https://{host}/products.json?limit=250&page={page}'
        if not allowed_page(url):break
        products=json.loads(fetch(url)).get('products',[])
        if not products:break
        for p in products:
            n=p['title'].lower()
            if brand=='Shelly' and not n.startswith('shelly'):continue
            if any(x in n for x in ['pack','bundle','course','gift','coupon','t-shirt','starter kit','family kit','combo','refurbish','renewed','recondition']):continue
            if re.search(r'\b[2-9]\s*x\b|\+',n):continue
            if not p.get('images'):continue
            normalized=re.sub(r'\b(white|black|ivory|blue|grey|gray|silver|anthracite)\b','',n)
            normalized=clean(normalized)
            if normalized in seen:continue
            seen.add(normalized);result.append((brand,p))
        if len(result)>=maximum:break
    return result[:maximum]

def save_asset(url):
    data=fetch(url)
    with Image.open(io.BytesIO(data)) as opened:
        opened.load()
        if opened.width<120 or opened.height<120:raise ValueError('Image too small')
        image=ImageOps.exif_transpose(opened).convert('RGBA' if 'A' in opened.getbands() else 'RGB')
        image.thumbnail((1400,1400))
        output=io.BytesIO();image.save(output,'WEBP',quality=86,method=4)
    asset=output.getvalue();sha=hashlib.sha256(asset).hexdigest()
    path=OUT/'assets'/(sha+'.webp')
    if not path.exists():path.write_bytes(asset)
    return {'path':'assets/'+path.name,'sha256':sha,'source_url':url,'width':image.width,'height':image.height}

def enrich(record):
    images=[];seen=set()
    for url in record['source_images']:
        if len(images)>=4:break
        try:
            asset=save_asset(url)
            if asset['sha256'] not in seen:seen.add(asset['sha256']);images.append(asset)
        except Exception as exc:errors.append({'url':url,'reason':str(exc),'type':'image'})
    record['images']=images
    documents=[]
    for doc in record['source_documents'][:2]:
        try:
            data=fetch(doc['url'])
            if not data.startswith(b'%PDF'):continue
            sha=hashlib.sha256(data).hexdigest();path=OUT/'assets'/(sha+'.pdf');path.write_bytes(data)
            documents.append({'title':doc['title'],'path':'assets/'+path.name,'sha256':sha,'source_url':doc['url']})
        except Exception as exc:errors.append({'url':doc['url'],'reason':str(exc),'type':'document'})
    record['documents']=documents
    return record

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--target',type=int,default=500);parser.add_argument('--workers',type=int,default=5);parser.add_argument('--metadata-only',action='store_true');args=parser.parse_args()
    CACHE.mkdir(parents=True,exist_ok=True);(OUT/'assets').mkdir(exist_ok=True)
    work=OUT/'records.json'
    if work.exists():records=json.loads(work.read_text(encoding='utf-8'))
    else:
        tasks=[]
        shop=soup_url('https://www.zipato.com/shop')
        tasks += [('zipato',u) for u in sorted({a['href'] for a in shop.select('a[href]') if '/product/' in a['href']})]
        for brand in ['SONOFF','Shelly']:
            candidates=shopify_candidates(brand,140)
            print(brand,'candidates',len(candidates),flush=True)
            tasks += [('shopify',p) for p in candidates]
        candidates=json.loads((ROOT/'catalogue_seed/tplink_candidates.json').read_text(encoding='utf-8'))
        tasks += [('tp',u) for u in candidates]
        print('Fetching',len(tasks),'official product pages',flush=True)
        def process(task):
            kind,value=task
            try:
                r=parse_zipato(value) if kind=='zipato' else parse_shopify(value) if kind=='shopify' else parse_tp(value)
                if len(r['specifications'])<4 or not r['source_images']:raise ValueError('Insufficient specifications or product images')
                return r
            except Exception as exc:
                errors.append({'url':value if isinstance(value,str) else value[0]+'/'+value[1]['handle'],'reason':str(exc),'type':'product'})
                return None
        records=[];seen=set()
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            for index,r in enumerate(pool.map(process,tasks),1):
                if r and r['key'] not in seen:records.append(r);seen.add(r['key'])
                if index%25==0:print('Product pages',index,'/',len(tasks),'qualified',len(records),flush=True)
        work.write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Qualified records:',len(records),'brands:',dict(Counter(r['brand'] for r in records)),flush=True)
    if args.metadata_only:return
    # Order by manufacturer, then interleave categories to avoid a one-category catalogue.
    groups={}
    for r in records:groups.setdefault((r['brand'],r['category']),[]).append(r)
    queue=[]
    while any(groups.values()):
        for key in sorted(groups):
            if groups[key]:queue.append(groups[key].pop(0))
    selected=[]
    for offset in range(0,len(queue),25):
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            for r in pool.map(enrich,queue[offset:offset+25]):
                if len(r['images'])>=2:selected.append(r)
                else:errors.append({'url':r['source_url'],'reason':'Fewer than two distinct downloadable images','type':'quality'})
        print('Complete products',len(selected),'/',args.target,'candidates checked',min(offset+25,len(queue)),flush=True)
        if len(selected)>=args.target:break
    selected=selected[:args.target]
    # Featured selection is editorial discovery, not a claim about rating or popularity.
    for brand in sorted({r['brand'] for r in selected}):
        items=[r for r in selected if r['brand']==brand]
        preferred=sorted(items,key=lambda r:(not any(k in r['name'].lower() for k in ['gen4','mini one','ax55','c200','zipatile2','tapo c']),r['name']))
        for r in preferred[:2]:r['is_featured']=True
    manifest={'schema_version':1,'generated_at':datetime.now(timezone.utc).isoformat(),'requested_count':args.target,'product_count':len(selected),'selection':'Official manufacturer records; no fabricated ratings, local prices or inventory; two distinct gallery images and four specification rows minimum.','products':selected}
    (OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    report={'requested':args.target,'ready':len(selected),'qualified_candidates':len(records),'brands':dict(Counter(r['brand'] for r in selected)),'categories':dict(Counter(r['category'] for r in selected)),'images':sum(len(r['images']) for r in selected),'specifications':sum(len(r['specifications']) for r in selected),'documents':sum(len(r['documents']) for r in selected),'errors':errors}
    (OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('FINAL',json.dumps({k:v for k,v in report.items() if k!='errors'}),flush=True)
    if len(selected)<args.target:raise SystemExit('Source-backed product target not reached; see report.json')

if __name__=='__main__':main()
