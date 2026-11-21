#!/usr/bin/env python3
"""Extract Moonshot USD/JPY 10-year insurer rates from its official HTML.

This is an experimental source adapter, not authorization to publish. The
output requires stage_rates.py checks before it may be consumed elsewhere.
"""
import argparse
import datetime as dt
import hashlib
from html.parser import HTMLParser
import json
import pathlib
import re
import urllib.request

from validate_rates import japanese_period

JST = dt.timezone(dt.timedelta(hours=9))
SOURCE_URL = "https://www.orixlife.co.jp/fx/whole-life/accumulation-interest-rate"

class ExtractText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []
        self.rows = []
        self._row = None
        self._cell = None
        self._in_main = False
        self._in_table = 0
    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._in_table += 1
        if tag == "tr" and self._in_table:
            self._row = []
        if tag in ("td", "th") and self._row is not None:
            self._cell = []
    def handle_data(self, data):
        if data.strip():
            self.text.append(data.strip())
        if self._cell is not None:
            self._cell.append(data)
    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append(re.sub(r"\s+", "", "".join(self._cell)))
            self._cell = None
        if tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None
        if tag == "table":
            self._in_table = max(0, self._in_table - 1)

DATE = re.compile(r"(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日\s*[～〜~－-]\s*(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日")
RATE = re.compile(r"^(-?\d+(?:\.\d+)?)\s*[％%]$")
TERM = re.compile(r"^10\s*年$")
CURRENCY = {"米ドル": "USD", "円": "JPY", "日本円": "JPY"}

def parse_official_html(raw, as_of, observed_at=None):
    parser = ExtractText()
    parser.feed(raw.decode("utf-8-sig", errors="strict"))
    text = "".join(parser.text)
    if "Moonshot" not in text or "積立利率" not in text:
        raise ValueError("Moonshot official rate heading was not found")
    periods = {(
        dt.date(int(m[1]), int(m[2]), int(m[3])),
        dt.date(int(m[4]), int(m[5]), int(m[6]))
    ) for m in DATE.finditer(text)}
    start, end = japanese_period(as_of)
    if (start, end) not in periods:
        raise ValueError(f"Current half-month rate period {start}–{end} not explicitly printed")
    if len(periods) > 1:
        raise ValueError("Ambiguous multiple rate periods in page")
    found = {}
    for cells in parser.rows:
        norm = [re.sub(r"\s+", "", x) for x in cells]
        if len(norm) != 3:
            continue
        currency, term, quoted = norm
        if currency not in CURRENCY or not TERM.fullmatch(term):
            continue
        m = RATE.fullmatch(quoted)
        if not m:
            raise ValueError(f"Invalid rate cell: {quoted[:40]}")
        unit = CURRENCY[currency]
        if unit in found:
            raise ValueError("Duplicate rate row for "+unit)
        found[unit] = (float(m.group(1)), quoted)
    if set(found) != {"USD", "JPY"}:
        raise ValueError("Expected exactly both Moonshot USD and JPY rows")
    timestamp = observed_at or dt.datetime.now(JST).isoformat(timespec="seconds")
    sha = hashlib.sha256(raw).hexdigest()
    output = []
    for unit in ("USD", "JPY"):
        value, quoted = found[unit]
        output.append({
            "product_id": "moon", "currency": unit, "label": "積立利率",
            "term": "10年", "lo": 0, "hi": 90, "value": value,
            "period": f"{start.isoformat()}～{end.isoformat()}",
            "source_url": SOURCE_URL, "source_sha256": sha,
            "source_locator": f"積立利率 table / {unit} / 10年",
            "source_value_text": quoted,
            "extraction_method": "official_html_table",
            "source_observed_at": timestamp,
            "payout": None
        })
    return {"schema_version": 1, "records": output,
            "publication_allowed": False,
            "note": "Unapproved source parser output; stage all conditions against full catalog and audit first."}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", type=pathlib.Path)
    ap.add_argument("--as-of", type=dt.date.fromisoformat)
    ap.add_argument("--out", type=pathlib.Path, default=pathlib.Path(__file__).resolve().parent/"moonshot-candidates.json")
    args = ap.parse_args()
    if args.html:
        raw = args.html.read_bytes()
    else:
        req = urllib.request.Request(SOURCE_URL, headers={"User-Agent":"Mozilla/5.0", "Accept":"text/html"})
        with urllib.request.urlopen(req, timeout=30) as r:
            if r.geturl() != SOURCE_URL:
                raise ValueError("Official source redirected; do not automatically accept new host/path")
            raw = r.read(2_000_001)
            if len(raw) > 2_000_000:
                raise ValueError("Response exceeds safety limit")
    day = args.as_of or dt.datetime.now(JST).date()
    output = parse_official_html(raw, day)
    args.out.write_text(json.dumps(output, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print("Moonshot source rows extracted (NOT PUBLISHED):", len(output["records"]))

if __name__ == "__main__":
    main()
