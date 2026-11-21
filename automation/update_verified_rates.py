#!/usr/bin/env python3
"""Unattended *public-rate-page only* updater for the existing v117 website.

Three official insurer products, 54 fixed dimensions. Reads archived v117
metadata for cross-checks; NEVER copies any of v117's embedded HTML, images,
PDFs, agency notes, or customer information into the public rate page.

Any source, layout, age/plan, period, payout, or confidentiality failure aborts
before a public file is written. Only rates-current.html can be replaced.
"""
import datetime as dt
import hashlib
import html
import json
import os
import pathlib
import re
import sys
import urllib.request

from extract_single_rates import extract, load_embedded_single
from parse_dfl import extract as parse_dfl, fetch as fetch_dfl, URLS as DFL_URLS
from parse_moonshot import parse_official_html, SOURCE_URL
from stage_rates import stage
from validate_rates import japanese_period

ROOT = pathlib.Path(__file__).resolve().parents[1]
JST=dt.timezone(dt.timedelta(hours=9))
PAGE=ROOT/"rates-current.html"
CATALOG=ROOT/"automation/sources.json"
EXPECTED={"present":22,"receive":30,"moon":2}
NAMES={
    "present":("第一フロンティア生命","プレミアプレゼント5"),
    "receive":("第一フロンティア生命","プレミアレシーブ2"),
    "moon":("オリックス生命","Moonshot（ムーンショット）"),
}
CURRENCIES={"USD":"米ドル","AUD":"豪ドル","JPY":"円"}
FORBIDDEN=("募集人用資料","社外秘","社内限り","推奨商品一覧表",
           "srcdoc=","data:image/","data:application/","base64,",
           "source_sha256","customer_name","v117/part","<iframe","<img","<object","<embed")
PERIOD_HEAD=re.compile(r"対象：20\d{2}年\d{1,2}月\d{1,2}日～\d{1,2}月\d{1,2}日")
DATE_NOTE=re.compile(r"20\d{2}年\d{1,2}月\d{1,2}日の公式サイト照合で確認した3商品・54条件")
TABLE=re.compile(r"(<tbody>)(.*?)(</tbody>)",re.S)
BEGIN=re.compile(r"const begins='20\d{2}-\d{2}-\d{2}';")
EXPIRES=re.compile(r"const expires='20\d{2}-\d{2}-\d{2}';")
CODE=re.compile(r"<script\b",re.I)

def source_rows(day):
    archive=extract(load_embedded_single(ROOT))
    if len(archive["catalog"])!=13 or len(archive["rates"])!=219:
        raise ValueError("v117 archived baseline has changed")
    sources=json.loads(CATALOG.read_text(encoding="utf-8"))
    by_source={x["id"]:x["url"] for x in sources["sources"]}
    records=[]
    audit=[]
    stamp=dt.datetime.now(JST).isoformat(timespec="seconds")
    for pid in EXPECTED:
        official_url=DFL_URLS[pid] if pid!="moon" else SOURCE_URL
        if by_source.get(pid)!=official_url:
            raise ValueError("Source URL not allowed for "+pid)
        if pid=="moon":
            req=urllib.request.Request(official_url,headers={"User-Agent":"Mozilla/5.0","Accept":"text/html"})
            with urllib.request.urlopen(req,timeout=30) as response:
                if response.geturl()!=official_url:
                    raise ValueError("Source redirect not approved")
                raw=response.read(2_000_001)
            if len(raw)>2_000_000:
                raise ValueError("Official page size limit")
            parsed=parse_official_html(raw,day,stamp)
        else:
            raw=fetch_dfl(pid)
            parsed=parse_dfl(raw,pid,day,stamp)
        if len(parsed["records"])!=EXPECTED[pid]:
            raise ValueError("Incomplete product source rows")
        records.extend(parsed["records"])
        audit.append({"id":pid,"status":"reachable","sha256":hashlib.sha256(raw).hexdigest(),
                      "checked_at_jst":stamp})
    staged=stage(archive,sources,{"sources":audit},{"records":records},day)
    if set(staged["source_products"])!=set(EXPECTED) or len(staged["records"])!=54:
        raise ValueError("Staged official values are incomplete")
    return staged

def escape(value):
    if isinstance(value,(dict,list,tuple)) or value is None:
        raise ValueError("Unsafe structured public field")
    s=str(value)
    if len(s)>90 or any(ord(c)<32 for c in s) or any(x in s for x in ("<",">","&","{","}","\"","'")):
        raise ValueError("Unsafe public field")
    if any(keyword in s for keyword in FORBIDDEN):
        raise ValueError("Private document indicator in public field")
    return html.escape(s,quote=True)

def render(template,validated,day):
    if validated.get("release_stage")!="VALIDATED_NOT_PUBLISHED":
        raise ValueError("Unvalidated insurer rate data")
    start,end=japanese_period(day)
    period=start.isoformat()+"～"+end.isoformat()
    if validated["period"]!=period or len(validated["records"])!=54:
        raise ValueError("Mismatched source effective period")
    if any(x in template for x in FORBIDDEN) or len(CODE.findall(template))!=1:
        raise ValueError("Existing public page has unknown assets/code")
    tr=[]
    count={pid:0 for pid in EXPECTED}
    keys=set()
    for record in validated["records"]:
        pid=record["product_id"]
        if pid not in EXPECTED or record["period"]!=period:
            raise ValueError("Unrecognized source product or mixed period")
        if record["currency"] not in CURRENCIES:
            raise ValueError("Unexpected currency")
        k=tuple(str(record[v]) for v in ("product_id","currency","label","term","lo","hi"))
        if k in keys:raise ValueError("Duplicate rate dimension")
        keys.add(k)
        count[pid]+=1
        val=record["value"]
        if not isinstance(val,(float,int)) or isinstance(val,bool) or not 0<=val<=20:
            raise ValueError("Impossible percentage")
        lo,hi=record["lo"],record["hi"]
        if not all(type(x)==int for x in (lo,hi)) or not 0<=lo<=hi<=120:
            raise ValueError("Invalid age interval")
        payout=record["payout"]
        if payout is not None:
            if set(payout)!={"male","female"} or any(type(payout[x]) not in (int,float) or not 0<=payout[x]<=20 for x in ("male","female")):
                raise ValueError("Invalid payout percent pair")
            payout_value=f'{payout["male"]:.2f}%／{payout["female"]:.2f}%'
        else:
            payout_value="—"
        values=(NAMES[pid][0],NAMES[pid][1],CURRENCIES[record["currency"]],record["label"],
                record["term"],f"{lo}～{hi}歳",f"{val:.2f}%",payout_value)
        tr.append("<tr>"+ "".join(("<td class=\"num\">" if i==6 else "<td>")+escape(value)+"</td>" for i,value in enumerate(values))+"</tr>")
    if count!=EXPECTED:
        raise ValueError("Incomplete official cell inventory")
    if len(TABLE.findall(template))!=1 or not PERIOD_HEAD.search(template) or not DATE_NOTE.search(template):
        raise ValueError("Unexpected current rate page structure")
    if len(BEGIN.findall(template))!=1 or len(EXPIRES.findall(template))!=1:
        raise ValueError("Missing effective-date guards")
    # Recheck official sources every day but do not commit a new page merely
    # to change the checked-at date when the period and 54 values match.
    current_table=TABLE.search(template)
    same_period=("const begins='"+start.isoformat()+"';" in template
                 and "const expires='"+end.isoformat()+"';" in template)
    if same_period and current_table and re.sub(r"\\s+","","".join(current_table.group(2).split()))==re.sub(r"\\s+","","".join(tr)):
        return template
    heading=f"対象：{start.year}年{start.month}月{start.day}日～{end.month}月{end.day}日"
    check=f"{day.year}年{day.month}月{day.day}日の公式サイト照合で確認した3商品・54条件"
    new=TABLE.sub(lambda m:m.group(1)+"\n"+"\n".join(tr)+m.group(3),template)
    new=PERIOD_HEAD.sub(heading,new)
    new=DATE_NOTE.sub(check,new)
    new=BEGIN.sub("const begins='"+start.isoformat()+"';",new)
    new=EXPIRES.sub("const expires='"+end.isoformat()+"';",new)
    if new.count("<tr><td>")+new.count("<tr><td class=\"num\">")!=54:
        raise ValueError("Rendered rates row count changed")
    if "自動更新ページではありません。" in new:\n        raise ValueError("Obsolete release notice in generated page")\n    if "全条件が一致したときだけ更新します。" not in new:\n        raise ValueError("Safe auto-update explanation missing")\n    if len(new.encode("utf-8"))>40_000 or len(CODE.findall(new))!=1 or any(x in new for x in FORBIDDEN):
        raise ValueError("Unsafe or unexpectedly large output")
    if new.count('id="rate-table" hidden style="display:none"')!=1 or "jstDate < begins || jstDate > expires" not in new:
        raise ValueError("Fail-closed effective-date protection missing")
    return new

def main():
    day=dt.datetime.now(JST).date()
    staged=source_rows(day)
    existing=PAGE.read_text(encoding="utf-8")
    new=render(existing,staged,day)
    if existing==new:
        print("VERIFIED NO CHANGE: 54 official rate conditions, effective period current.")
        return
    if os.environ.get("AUTO_RATE_DRY_RUN")=="1":
        print("DRY RUN PASS: 54 official rate conditions, publication not performed.")
        return
    # Atomically replace only the small public rate-only page. The CI job may
    # commit only this file after the privacy and HTML regression tests pass.
    temp=PAGE.with_name("rates-current.html.tmp")
    try:
        temp.write_text(new,encoding="utf-8")
        temp.replace(PAGE)
    finally:
        if temp.exists():temp.unlink()
    print("UPDATED rates-current.html only: 54 official conditions, "+staged["period"])

if __name__=="__main__":
    try: main()
    except Exception as exc:
        print("NO RATE PUBLICATION: "+type(exc).__name__+"; official source or privacy checks failed.",file=sys.stderr)
        raise SystemExit(1)
