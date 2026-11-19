#!/usr/bin/env python3
"""Official Daiichi Frontier HTML rate-table adapters (no publishing).

Parse narrowly scoped official rate tables. Reject changed layout, missing
conditions, wrong half-month, malformed rates and missing payout values.
Stage against independent v117 dimension inventory before any release.
"""
import datetime as dt
import hashlib
import json
import re
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urlsplit

from validate_rates import japanese_period

URLS = {
    "present": "https://www.d-frontier-life.co.jp/products/index_hendo_shushin_choice_20_6.html?agency=227&product=224",
    "receive": "https://www.d-frontier-life.co.jp/products/index_recurrining_payment_shushin_23.html?agency=132&product=204",
}
CURRENCIES = {"米ドル": "USD", "豪ドル": "AUD", "円": "JPY"}
DATE = re.compile(r"(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日\s*[～〜~－-]\s*(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日")
AGE = re.compile(r"^(\d+)歳?～(\d+)歳$")
RATE = re.compile(r"^(\d+(?:\.\d+)?)%$")
TERM = re.compile(r"^\d+年$")
JST = dt.timezone(dt.timedelta(hours=9))

class OfficialTableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables = []
        self.headings = []
        self.all_text = []
        self.heading = None
        self.table = None
        self.row = None
        self.cell = None
    def handle_starttag(self, tag, attrs):
        if tag in ("h1", "h2", "h3", "h4"):
            self.heading = []
        if tag == "table":
            self.table = {"heading": self.headings[-1] if self.headings else "", "rows": []}
        if tag == "tr" and self.table is not None:
            self.row = []
        if tag in ("td", "th") and self.row is not None:
            self.cell = []
    def handle_data(self, data):
        if data.strip():
            self.all_text.append(data.strip())
        if self.heading is not None:
            self.heading.append(data)
        if self.cell is not None:
            self.cell.append(data)
    def handle_endtag(self, tag):
        if tag in ("h1", "h2", "h3", "h4") and self.heading is not None:
            self.headings.append(re.sub(r"\s+", "", "".join(self.heading)))
            self.heading = None
        if tag in ("td", "th") and self.cell is not None and self.row is not None:
            self.row.append(re.sub(r"\s+", "", "".join(self.cell)))
            self.cell = None
        if tag == "tr" and self.row is not None and self.table is not None:
            self.table["rows"].append(self.row)
            self.row = None
        if tag == "table" and self.table is not None:
            self.tables.append(self.table)
            self.table = None

def parse_rate(s):
    m = RATE.fullmatch(s)
    if not m:
        raise ValueError("Missing or nonnumeric percent rate: " + repr(s[:40]))
    value = float(m.group(1))
    if not 0 <= value <= 20:
        raise ValueError("Rate out of bounds")
    return value

def official_period(parser, as_of):
    text = " ".join(parser.all_text)
    matches = {(dt.date(*map(int,m.groups()[:3])),dt.date(*map(int,m.groups()[3:]))) for m in DATE.finditer(text)}
    expected = japanese_period(as_of)
    if expected not in matches or len(matches) != 1:
        raise ValueError(f"Official effective period missing or ambiguous: {matches}")
    return f"{expected[0]}～{expected[1]}"

def selected_tables(parser, product):
    headings = (
        ["死亡保障プラン","認知症・介護プラン(告知あり)","認知症・介護プラン(告知なし)"]
        if product == "present" else ["基本プラン","指数プラン"]
    )
    result = {}
    for t in parser.tables:
        if t["heading"] in headings:
            if t["heading"] in result:
                raise ValueError("Duplicated official rate plan")
            result[t["heading"]] = t["rows"]
    if set(result) != set(headings):
        raise ValueError("Expected official plan tables missing")
    return result

def extract(raw, product, as_of, observed_at=None):
    if product not in URLS:
        raise ValueError("Unrecognized product")
    p = OfficialTableParser()
    p.feed(raw.decode("utf-8-sig"))
    title = "".join(p.headings)
    expected_title = "積立利率変動型終身保険（20）" if product=="present" else "定期支払金付積立利率変動型終身保険（23）"
    if expected_title not in title:
        raise ValueError("Wrong insurer product heading")
    period=official_period(p,as_of)
    tables=selected_tables(p,product)
    digest=hashlib.sha256(raw).hexdigest()
    observed=observed_at or dt.datetime.now(JST).isoformat(timespec="seconds")
    records=[]
    for heading, rows in tables.items():
        currency = None
        age = None
        term = None
        for rownum, row in enumerate(rows[1 if product=="present" else 2:], start=2 if product=="present" else 3):
            if not row:
                continue
            currency_cells=[x for x in row if x in CURRENCIES]
            if len(currency_cells)>1:
                raise ValueError("Ambiguous currency")
            if currency_cells:
                currency=CURRENCIES[currency_cells[0]]
            age_cells=[AGE.fullmatch(x) for x in row]
            age_cells=[x for x in age_cells if x]
            if len(age_cells)>1:
                raise ValueError("Ambiguous age band")
            if age_cells:
                age=tuple(int(x) for x in age_cells[0].groups())
            if not currency or not age:
                raise ValueError(f"Missing currency or age band in {heading} row {rownum}")
            if product=="present":
                term_cells=[x for x in row if TERM.fullmatch(x)]
                if age_cells:
                    if len(term_cells)!=1:
                        raise ValueError("Expected one guarantee term for age-band row")
                    term=term_cells[0]
                if not term:
                    raise ValueError("Missing guarantee term")
                if heading=="死亡保障プラン":
                    suppress=[x for x in row if x in ("9ヵ月","5年")]
                    if len(suppress)!=1:
                        raise ValueError("Death-plan suppression period missing")
                    label="死亡保障／保障抑制"+suppress[0]
                else:
                    label="認知症・介護／告知あり" if "告知あり" in heading else "認知症・介護／告知なし"
                percent=[x for x in row if "%" in x or x=="-"]
                if len(percent)!=1:
                    raise ValueError("Expected exactly one accumulated interest rate")
                value=parse_rate(percent[0])
                payout=None
            else:
                label=heading
                term="10年"
                percent=[x for x in row if "%" in x or x=="-"]
                if len(percent)!=3:
                    raise ValueError(f"Expected accumulated rate plus two payout rates: {heading}, {rownum}")
                value=parse_rate(percent[0])
                payout={"male":parse_rate(percent[1]),"female":parse_rate(percent[2])}
            rec={
                "product_id":product, "currency":currency, "label":label,
                "term":term, "lo":age[0], "hi":age[1],
                "value":value, "period":period, "payout":payout,
                "source_url":URLS[product], "source_sha256":digest,
                "source_locator":f"{heading} table row {rownum} {currency} {age[0]}-{age[1]}",
                "source_value_text":percent[0],
                "extraction_method":"official_html_table", "source_observed_at":observed
            }
            if payout is not None:
                rec["payout_source_locator_male"]=f"{heading} row {rownum} male {percent[1]}"
                rec["payout_source_locator_female"]=f"{heading} row {rownum} female {percent[2]}"
            records.append(rec)
    expected_count = 22 if product=="present" else 30
    if len(records)!=expected_count:
        raise ValueError(f"{product}: expected {expected_count} rows, got {len(records)}")
    keys={(r["currency"],r["label"],r["term"],r["lo"],r["hi"]) for r in records}
    if len(keys)!=expected_count:
        raise ValueError("Duplicate rate dimensions")
    return {"schema_version":1, "publication_allowed":False,"records":records,
            "note":"Experimental official HTML parsing; must pass stage and release checks."}

def fetch(product):
    url=URLS[product]
    req=urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0","Accept":"text/html"})
    with urllib.request.urlopen(req, timeout=30) as response:
        if response.geturl()!=url:
            raise ValueError("Official rate page unexpectedly redirected")
        data=response.read(2_000_001)
        if len(data)>2_000_000:
            raise ValueError("Official rate HTML exceeds limit")
        return data
