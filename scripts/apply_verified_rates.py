#!/usr/bin/env python3
"""Apply approved rates to the existing split GitHub Pages app.
No approved entries = no change. This does NOT scrape or approve official rates.
"""
import base64
import copy
import datetime as dt
import html
import json
import re
import sys
from pathlib import Path

JST = dt.timezone(dt.timedelta(hours=9))
PART = re.compile(r'^window\.__insuranceParts\.push\("([A-Za-z0-9+/=]+)"\);?\s*$', re.S)
SINGLE = re.compile(r'(<iframe\b[^>]*\bid="single"[^>]*\bsrcdoc=")(.*?)(")', re.S)
PREFIX = 'const PRODUCTS='

def apply(outer, rows, today=None):
    today = today or dt.datetime.now(JST).date()
    if not rows:
        return outer, 0
    matches = list(SINGLE.finditer(outer))
    if len(matches) != 1:
        raise ValueError(f'Expected one single-premium iframe; found {len(matches)}')
    match = matches[0]
    inner = html.unescape(match.group(2))
    if inner.count(PREFIX) != 1:
        raise ValueError('Cannot uniquely identify PRODUCTS data')
    a = inner.index(PREFIX) + len(PREFIX)
    products, offset = json.JSONDecoder().raw_decode(inner[a:])
    if not isinstance(products, list) or len(products) < 8:
        raise ValueError('Unexpected product layout')
    product_map = {p['id']: p for p in products}
    if len(product_map) != len(products):
        raise ValueError('Duplicate product IDs')
    changed = 0
    for item in rows:
        if item['verification'] != 'approved':
            continue
        start, end = (dt.date.fromisoformat(item[k]) for k in ('valid_from','valid_to'))
        if not (start <= today <= end):
            continue
        p = product_map.get(item['product_id'])
        if p is None:
            raise ValueError(f'Unknown product: {item["product_id"]}')
        key = (item['currency'],item['label'],item['term'],item['lo'],item['hi'])
        def same(r):
            return (r.get('currency'),r.get('label'),r.get('term'),r.get('lo'),r.get('hi')) == key
        candidates = [r for r in p['rates'] if same(r)]
        if not candidates:
            raise ValueError(f'No matching condition for {p["id"]}: {key}')
        period = f'{start.isoformat()}～{end.isoformat()}'
        existing = [r for r in candidates if r.get('period') == period]
        if len(existing) > 1:
            raise ValueError('Duplicate period/condition in template')
        if existing:
            target = existing[0]
        else:
            target = copy.deepcopy(max(candidates,key=lambda r:r.get('period','')))
            p['rates'].append(target)
        new = copy.deepcopy(target)
        new.update(value=item['rate_percent'],period=period,
                   extra='公式出典・条件照合済み。'+item['source_label'],
                   scope='公式利率。加入可否・手数料等は商品資料で要確認')
        if 'payout' in item:
            new['payout'] = item['payout']
        elif isinstance(target.get('payout'),dict):
            raise ValueError('Gender-specific payout rates must be supplied')
        if new != target:
            target.clear()
            target.update(new)
            changed += 1
    if not changed:
        return outer, 0
    newer = inner[:a]+json.dumps(products,ensure_ascii=False,separators=(',',':'))+inner[a+offset:]
    return outer[:match.start()]+match.group(1)+html.escape(newer,quote=True)+match.group(3)+outer[match.end():],changed

def read_parts(folder):
    files=sorted(folder.glob('part[0-9][0-9][0-9].js'))
    if len(files)<10 or [p.name for p in files]!=[f'part{i:03d}.js' for i in range(len(files))]:
        raise ValueError('Missing parts')
    chunks=[]
    for file in files:
        m=PART.fullmatch(file.read_text(encoding='utf-8'))
        if not m:
            raise ValueError(f'Unexpected part format: {file.name}')
        chunks.append(m.group(1))
    return base64.b64decode(''.join(chunks),validate=True).decode('utf-8'),files

def write_parts(outer, files):
    encoded=base64.b64encode(outer.encode('utf-8')).decode('ascii')
    size=400000
    parts=[encoded[i:i+size] for i in range(0,len(encoded),size)]
    if len(parts)!=len(files):
        raise ValueError(f'Part count changed ({len(files)} -> {len(parts)}); abort')
    for file,part in zip(files,parts):
        file.write_text('window.__insuranceParts.push("'+part+'");',encoding='utf-8')

if __name__=='__main__':
    data=json.loads(Path('rates/approved.json').read_text(encoding='utf-8'))
    rows=data['rates']
    if not rows:
        print('No approved rates; app unchanged')
        sys.exit(0)
    from validate_rates import validate
    errors=validate(rows)
    if errors:
        raise SystemExit('\n'.join(errors))
    old,files=read_parts(Path('parts'))
    newer,count=apply(old,rows)
    if count:
        write_parts(newer,files)
    print(f'Updated {count} independently approved rate records')
