#!/usr/bin/env python3
"""Produce an auditable coverage dashboard for bundled single-premium rates.

This report never makes archived values current. It reports whether a quoted
row has an effective window matching the Japan-local check date, and whether
the source locator has been independently verified (it has not here).
"""
import argparse
import datetime as dt
import json
import pathlib
from collections import Counter

JST = dt.timezone(dt.timedelta(hours=9))

def coverage(snapshot, day):
    if snapshot.get("publication_allowed") is not False:
        raise ValueError("snapshot must be explicitly non-publishable")
    by_product = {}
    for product in snapshot["catalog"]:
        ident = product["id"]
        rows = [r for r in snapshot["rates"] if r["product_id"] == ident]
        in_window = [r for r in rows if r["period"].split("～")[0] <= day.isoformat() <= r["period"].split("～")[-1]]
        periods = dict(Counter(r["period"] for r in rows))
        by_product[ident] = {
            "company": product["company"], "name": product["name"],
            "recorded_conditions": len(rows), "within_effective_window": len(in_window),
            "source_verified": False,
            "publishable_conditions": 0,
            "periods": periods,
            "status": "PERIOD_CANDIDATES_NOT_SOURCE_VERIFIED" if in_window else "NO_CURRENT_RATE"
        }
    return {"schema_version": 1, "as_of_jst": day.isoformat(),
            "rate_publication_allowed": False,
            "reason": "Only original embedded dates checked; exact official source and all dimensions not independently validated.",
            "products": by_product}

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--snapshot", type=pathlib.Path, default=pathlib.Path(__file__).resolve().parent / "v117-rate-snapshot.json")
    p.add_argument("--out", type=pathlib.Path, default=pathlib.Path(__file__).resolve().parent / "rate-coverage.json")
    args = p.parse_args()
    date = dt.datetime.now(JST).date()
    report = coverage(json.loads(args.snapshot.read_text(encoding="utf-8")), date)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    counts = Counter(v["status"] for v in report["products"].values())
    print(f"Period coverage as of {date}: {dict(counts)}; no conditions approved to publish")

if __name__ == "__main__":
    main()
