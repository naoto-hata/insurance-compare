#!/usr/bin/env python3
"""Monitor official insurer rate pages. Audit ≠ rate extraction or publication."""
import datetime as dt
import hashlib
import json
import pathlib
import os
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent
CONFIG = ROOT / "sources.json"
OUTPUT = ROOT / "source-audit.json"
MAX_BYTES = 3_000_000
ALLOWED_HOSTS = ["www.metlife.co.jp","www.d-frontier-life.co.jp","www2.axa.co.jp","www.manulife.co.jp","www.medicarelife.com","customer.fwdlife.co.jp","www.orixlife.co.jp","www.gib-life.co.jp","www.sonylife.co.jp"]
JST = dt.timezone(dt.timedelta(hours=9))

def check(source):
    url = source["url"]
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
        return {"status": "blocked", "reason": "URL not on official allowlist"}
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "InsuranceRateSourceAudit/1.0 (public-data verification)", "Accept": "text/html,application/pdf,*/*"})
        with urllib.request.urlopen(req, timeout=25) as response:
            final = urllib.parse.urlsplit(response.geturl())
            if final.scheme != "https" or final.hostname not in ALLOWED_HOSTS:
                return {"status": "blocked", "reason": "Redirected outside official allowlist"}
            data = response.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                return {"status": "error", "reason": "Source exceeds safety size limit"}
            if source["id"] == "moon":
                cache = pathlib.Path(os.environ.get("RATE_SOURCE_CACHE", "/tmp/insurance-rate-source-cache"))
                cache.mkdir(parents=True, exist_ok=True)
                (cache / "moon.html").write_bytes(data)
            return {"status": "reachable", "http_status": response.status,
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "content_type": response.headers.get("Content-Type", "").split(";")[0]}
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        return {"status": "error", "reason": str(exc)[:240]}

def main():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    prior = {}
    if OUTPUT.exists():
        try:
            prior = {r["id"]: r for r in json.loads(OUTPUT.read_text(encoding="utf-8")).get("sources", [])}
        except (ValueError, KeyError):
            pass
    now = dt.datetime.now(JST).isoformat(timespec="seconds")
    rows = []
    for source in config["sources"]:
        result = check(source)
        old = prior.get(source["id"], {})
        row = {**source, **result, "checked_at_jst": now,
               "rate_values_verified": False, "automatically_published": False}
        row["changed_since_previous_check"] = (
            result.get("sha256") != old.get("sha256")
            if result.get("sha256") and old.get("sha256") else None
        )
        rows.append(row)
    OUTPUT.write_text(json.dumps({"schema_version": 1, "checked_at_jst": now,
                   "description": "Source reachability audit. No verified insurance rates; never use as quotation data.",
                   "sources": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("\n".join(f'{r["id"]}: {r["status"]} changed={r["changed_since_previous_check"]}' for r in rows))
    if all(r["status"] != "reachable" for r in rows):
        raise SystemExit("No official sources reachable")

if __name__ == "__main__":
    main()
