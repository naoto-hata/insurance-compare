#!/usr/bin/env python3
"""Verify safety and effective-period boundaries in the v117 public rate page."""
from pathlib import Path
import re
import sys
import datetime as dt

ROOT=Path(__file__).resolve().parents[1]
PUBLIC_RATE=ROOT/"rates-current.html"
PUBLIC_INDEX=ROOT/"index.html"
FORBIDDEN=("募集人用資料","社外秘","社内限り","推奨商品一覧表",
           "srcdoc=","data:image/","data:application/","base64,",
           "source_sha256","customer_name","v117/part","<iframe","<img","<object")

def verify():
    index=PUBLIC_INDEX.read_text(encoding="utf-8")
    page=PUBLIC_RATE.read_text(encoding="utf-8")
    if len(page.encode("utf-8"))>40_000:
        raise ValueError("Public rate page unexpected growth")
    if any(x in page for x in FORBIDDEN):
        raise ValueError("Private material or embedded asset in public rates")
    if page.count("<tr><td>")!=54:
        raise ValueError("Incorrect official rate row count")
    if not all(x in page for x in ("プレミアプレゼント5","プレミアレシーブ2","Moonshot（ムーンショット）")):
        raise ValueError("Missing rate product")
    begin=re.search(r"const begins='(20\d{2}-\d{2}-\d{2})';",page)
    expiry=re.search(r"const expires='(20\d{2}-\d{2}-\d{2})';",page)
    if not begin or not expiry:
        raise ValueError("Missing effective-date boundaries")
    start=dt.date.fromisoformat(begin.group(1))
    end=dt.date.fromisoformat(expiry.group(1))
    if start.day not in (1,16) or (end-start).days<12 or (end-start).days>15:
        raise ValueError("Invalid half-monthly effective interval")
    if start.day==1 and end.day!=15:
        raise ValueError("First half must end on day 15")
    if start.day==16 and end.month==start.month and (end+dt.timedelta(days=1)).day!=1:
        raise ValueError("Second half must end at month end")
    title=f"対象：{start.year}年{start.month}月{start.day}日～{end.month}月{end.day}日"
    if title not in page:
        raise ValueError("Visible date disagrees with JS expiry gate")
    required=(
        'id="rate-expired"','id="rate-table" hidden style="display:none"',
        'rateTable.hidden=true','rateTable.hidden=false',
        '<noscript>',"jstDate < begins || jstDate > expires",
        "timeZone:'Asia/Tokyo'",'formatToParts',
    )
    if not all(x in page for x in required):
        raise ValueError("Fail-closed JST rate gate missing")
    if "rates-current.html" not in index or "公式利率一覧・最新の適用状況を確認" not in index:
        raise ValueError("V117 home missing evergreen rate link")
    if len(re.findall(r'<script\b',page,re.I))!=1:
        raise ValueError("Unexpected JS in public rate page")
    if re.search(r'<(?:iframe|object|embed|img|link)\b',page,re.I):
        raise ValueError("Forbidden embedded element")
    return True

if __name__=="__main__":
    try:verify()
    except (ValueError,OSError,UnicodeError) as exc:
        print("V117 RATE SAFETY CHECK FAILED:",type(exc).__name__,file=sys.stderr)
        sys.exit(1)
    print("PASS: v117 54-rate public page and dynamic JST period guard.")
