#!/usr/bin/env python3
"""Fail-closed validation of proposed official rate records before publication.
A successful run validates structure, not authenticity: human/source-specific
verification is separately required before rates may be marked published.
"""
import datetime as dt
import json
import sys
from pathlib import Path

ALLOWED = {"USD", "AUD", "JPY", "EUR", "NZD"}
def validate(rows, today=None):
    today = today or dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date()
    errors, keys = [], set()
    if not isinstance(rows, list): return ["rates must be a list"]
    for i, r in enumerate(rows):
        where = f"rates[{i}]"
        if not isinstance(r, dict):
            errors.append(f"{where}: expected object"); continue
        needed = ("product_id", "currency", "condition_id", "label", "term", "lo", "hi", "rate_percent", "valid_from", "valid_to", "official_url", "verified_on", "verification", "source_label")
        for key in needed:
            if key not in r: errors.append(f"{where}: missing {key}")
        if any(key not in r for key in needed): continue
        if r["currency"] not in ALLOWED: errors.append(f"{where}: unexpected currency")
        if type(r["rate_percent"]) not in (float, int) or not (0 <= r["rate_percent"] <= 30):
            errors.append(f"{where}: invalid rate_percent")
        if not isinstance(r["label"], str) or not r["label"].strip() or not isinstance(r["term"], str) or not r["term"].strip():
            errors.append(f"{where}: label and term required")
        if type(r["lo"]) is not int or type(r["hi"]) is not int or not (0 <= r["lo"] <= r["hi"] <= 120):
            errors.append(f"{where}: invalid age range")
        if "payout" in r:
            payout = r["payout"]
            if payout is not None and (not isinstance(payout, dict) or
                set(payout) != {"male","female"} or
                any(type(v) not in (float,int) or not 0 <= v <= 30 for v in payout.values())):
                errors.append(f"{where}: payout must contain valid male and female rates")
        try:
            start, end, checked = [dt.date.fromisoformat(r[k]) for k in ("valid_from","valid_to","verified_on")]
            if start > end: errors.append(f"{where}: reversed period")
            if checked > today: errors.append(f"{where}: future verification")
            if (end-start).days > 370: errors.append(f"{where}: unusually long period")
        except (ValueError, TypeError):
            errors.append(f"{where}: invalid dates")
        if not (isinstance(r["official_url"],str) and r["official_url"].startswith("https://")):
            errors.append(f"{where}: source must be HTTPS URL")
        if r["verification"] not in ("pending","approved"):
            errors.append(f"{where}: verification must be pending or approved")
        if not isinstance(r["source_label"],str) or len(r["source_label"]) < 5:
            errors.append(f"{where}: source_label required")
        key=(r["product_id"],r["currency"],r["label"],r["term"],r["lo"],r["hi"],r["valid_from"],r["valid_to"])
        if key in keys: errors.append(f"{where}: duplicate condition")
        keys.add(key)
    return errors

if __name__ == "__main__":
    path=Path(sys.argv[1] if len(sys.argv)>1 else "rates/proposed.json")
    rows=json.loads(path.read_text(encoding="utf-8"))["rates"]
    errors=validate(rows)
    if errors:
        print("\n".join(errors),file=sys.stderr)
        sys.exit(1)
    print(f"Validated {len(rows)} proposed records; this is NOT official-source verification.")
