#!/usr/bin/env python3
"""Audit embedded public app revision and current rates without changing anything."""
import datetime as dt
import html
import json
import re
import sys
from pathlib import Path
from apply_verified_rates import read_parts, SINGLE, PREFIX

JST=dt.timezone(dt.timedelta(hours=9))
today=dt.datetime.now(JST).date()
outer,files=read_parts(Path("parts"))
m=SINGLE.search(outer)
if not m or len(SINGLE.findall(outer)) != 1:
    raise SystemExit("FAIL: single-premium iframe missing")
inner=html.unescape(m.group(2))
if inner.count(PREFIX)!=1:
    raise SystemExit("FAIL: rate table missing")
products=json.JSONDecoder().raw_decode(inner.split(PREFIX,1)[1])[0]
active=[]
expired=[]
for p in products:
    for r in p.get("rates",[]):
        period=r.get("period","")
        dates=re.findall(r'\d{4}-\d{2}-\d{2}',period)
        if len(dates)==2:
            try:
                start,end=map(dt.date.fromisoformat,dates)
            except ValueError:
                continue
            if start<=today<=end: active.append((p["id"],r))
            elif end<today: expired.append((p["id"],r))
revision=re.search(r'第(\d+)版',outer)
release=int(revision.group(1)) if revision else None
report={"as_of":today.isoformat(),"revision":release,"total_products":len(products),
        "active_rate_records":len(active),"expired_rate_records":len(expired),
        "active_products":sorted(set(k for k,_ in active)),
        "parts":len(files),"automated_verification":"not performed"}
Path("rates/public-audit.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(report,ensure_ascii=False,indent=2))
if release is None:
    raise SystemExit("FAIL: release marker missing")
if not active:
    raise SystemExit("FAIL: no rates with a current valid period")
