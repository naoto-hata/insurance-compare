#!/usr/bin/env python3
"""Read-only safety regression for the *public* v117 rate-only page.

Only examines two small public entrypoints, not confidential embedded app
payloads. It never produces files, artifacts, commits or logs of source text.
"""
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
PUBLIC_RATE=ROOT/"rates-current.html"
PUBLIC_INDEX=ROOT/"index.html"
END="2026-11-30"
FORBIDDEN=("募集人用資料","社外秘","社内限り","推奨商品一覧表",
           "srcdoc=","data:image/","data:application/","base64,",
           "source_sha256","customer_name","v117/part")

def verify():
    index=PUBLIC_INDEX.read_text(encoding="utf-8")
    page=PUBLIC_RATE.read_text(encoding="utf-8")
    if len(page.encode("utf-8"))>40_000:
        raise ValueError("Public rate page unexpected growth")
    if any(word in page for word in FORBIDDEN):
        raise ValueError("Non-public asset or private material marker in rates page")
    if page.count("<tr><td>")!=54:
        raise ValueError("Rate table does not contain exactly 54 approved historical rows")
    for label in ("プレミアプレゼント5","プレミアレシーブ2","Moonshot（ムーンショット）"):
        if label not in page:
            raise ValueError("Expected insurer product missing")
    if not all(s in page for s in (
        'id="rate-expired"', 'id="rate-table" hidden style="display:none"',
        'rateTable.hidden=true', 'rateTable.hidden=false',
        '<noscript>', '2026-11-16', "jstDate < begins || jstDate > expires", END, "timeZone:'Asia/Tokyo'",
        'formatToParts', '現在の適用期間外です'
    )):
        raise ValueError("Fail-closed JST expiry protection missing")
    if "rates-current.html" not in index or "利率の確認待ち" not in index:
        raise ValueError("V117 main page does not link to expiry-aware rate table")
    if "formatToParts" not in index or END not in index:
        raise ValueError("Main-page rate link expiry protection missing")
    if len(re.findall(r'<script\b',page,re.I))!=1:
        raise ValueError("Unexpected executable code count in public rates page")
    if re.search(r'<(?:iframe|object|embed|img|link)\b',page,re.I):
        raise ValueError("External/embedded material not allowed in rate-only view")
    return True

if __name__=="__main__":
    try:
        verify()
    except (ValueError,OSError,UnicodeError) as exc:
        print("V117 PUBLIC RATE SAFETY CHECK FAILED:",type(exc).__name__,file=sys.stderr)
        sys.exit(1)
    print("PASS: v117 public link, 54 rate rows, no embedded assets, and JST expiry safeguards.")
