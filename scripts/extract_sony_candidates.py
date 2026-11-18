#!/usr/bin/env python3
"""Discover Sony Life public rates and stage as UNAPPROVED evidence only.

No date is inferred from today's clock. A valid policy-effective period must
be stated explicitly in source data and independently verified before release.
"""
import datetime as dt
import hashlib
import json
import re
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

URL="https://www.sonylife.co.jp/rate/accumulation_interest_rate"

class TableReader(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows=[]; self.in_row=False; self.in_cell=False
        self.cells=[]; self.cell=[]
    def handle_starttag(self,tag,attrs):
        if tag=="tr":
            self.in_row=True; self.cells=[]
        if self.in_row and tag in ("td","th"):
            self.in_cell=True; self.cell=[]
    def handle_data(self,data):
        if self.in_cell: self.cell.append(data)
    def handle_endtag(self,tag):
        if self.in_row and tag in ("td","th"):
            self.cells.append(re.sub(r"\s+"," "," ".join(self.cell)).strip())
            self.in_cell=False
        if tag=="tr" and self.in_row:
            if self.cells: self.rows.append(self.cells)
            self.in_row=False

def collect(raw):
    parser=TableReader()
    parser.feed(raw)
    rates=[]
    for cells in parser.rows:
        for val in cells:
            for m in re.finditer(r'(?<!\d)(\d+(?:\.\d+)?)\s*[％%]',val):
                amount=float(m.group(1))
                if 0<=amount<=30: rates.append(amount)
    return parser.rows,rates

def main():
    req=urllib.request.Request(URL,headers={"User-Agent":"Mozilla/5.0 (compatible; RateEvidenceDiscovery/1.0)"})
    with urllib.request.urlopen(req,timeout=30) as response:
        if response.status!=200: raise ValueError("Non-200 source")
        content=response.read(2_000_000)
    raw=content.decode("utf-8",errors="replace")
    rows,rates=collect(raw)
    result={
        "source_url":URL,
        "retrieved_at":dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_sha256":hashlib.sha256(content).hexdigest(),
        "approval":"pending",
        "effective_period":None,
        "reason":"Cannot infer effective dates or exact age/currency/period mapping from unvalidated HTML rows",
        "percent_values_seen":rates[:60],
        "table_rows_preview":rows[:45]
    }
    Path("sony-evidence.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"Found {len(rates)} percentage-like values; all remain pending")
if __name__=="__main__": main()
