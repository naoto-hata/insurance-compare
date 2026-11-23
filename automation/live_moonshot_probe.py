#!/usr/bin/env python3
"""Live read-only Moonshot adapter exercise; does not publish or alter repo files."""
import datetime as dt
import hashlib
import json
import pathlib
import sys
import urllib.request
from parse_moonshot import SOURCE_URL, parse_official_html
from stage_rates import stage
from validate_rates import japanese_period

JST = dt.timezone(dt.timedelta(hours=9))
ROOT = pathlib.Path(__file__).resolve().parent

def main():
    now = dt.datetime.now(JST)
    request = urllib.request.Request(SOURCE_URL, headers={
        "User-Agent": "Mozilla/5.0 (compatible; InsuranceCompareRateVerifier/1.0)",
        "Accept": "text/html"})
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.geturl().split("?")[0] != SOURCE_URL:
            raise ValueError(f"Unexpected source redirect: {response.geturl()}")
        data = response.read(2_000_001)
    if len(data) > 2_000_000:
        raise ValueError("Official HTML exceeds safety limit")
    parsed = parse_official_html(data, now.date(), now.isoformat(timespec="seconds"))
    records = parsed["records"]
    digest = hashlib.sha256(data).hexdigest()
    snapshot = json.loads((ROOT / "v117-rate-snapshot.json").read_text(encoding="utf-8"))
    sources = json.loads((ROOT / "sources.json").read_text(encoding="utf-8"))
    audit = {"sources": [{"id":"moon", "status":"reachable", "sha256":digest,
             "checked_at_jst":now.isoformat(timespec="seconds")}]}
    result = stage(snapshot, sources, audit, parsed, now.date())
    period = str(japanese_period(now.date()))
    print(f"LIVE ADAPTER PASS (staging only, never published): {len(result['records'])} rows, {period}")
    for row in result["records"]:
        print(f"{row['currency']} {row['term']}: {row['value']}% | {row['period']}")
    print("No data changed on GitHub Pages or the release branch")

if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"LIVE ADAPTER NOT VERIFIED: {type(error).__name__}: {error}", file=sys.stderr)
        sys.exit(1)
