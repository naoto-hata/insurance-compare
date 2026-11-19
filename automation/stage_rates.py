#!/usr/bin/env python3
"""Safely stage new half-month rate rows before any public-site deployment.

The updater is intentionally fail-closed:
- Product IDs and exact rate dimensions must already exist in v117's catalog.
- Every rate for a *selected* product must be supplied together (no partial
  updates that silently keep last period's values).
- The source URL must match that product's registered official rate URL.
- An independently obtained source SHA-256 must match the source audit.
- Source-specific extraction evidence is required (a concrete locator and
  machine-readable text per condition). It is not independent human verification.
- The period must be the current Japan-local 1–15 / 16–last-day window.
- No bundled 2026 historical rate is used as a fallback.

This stage does not itself fetch or publish insurance rates.
"""
import argparse
import datetime as dt
import hashlib
import json
import pathlib
import re
import sys
from collections import defaultdict
from urllib.parse import urlsplit

from validate_rates import japanese_period

JST = dt.timezone(dt.timedelta(hours=9))
HEX = re.compile(r"^[0-9a-f]{64}$")
REQUIRED_RECORD_FIELDS = (
    "product_id", "currency", "label", "term", "lo", "hi",
    "value", "period", "source_url", "source_sha256",
    "source_locator", "source_value_text", "extraction_method",
    "source_observed_at", "payout",
)

def dimension(row):
    return tuple(str(row[k]) for k in ("currency", "label", "term", "lo", "hi"))

def fail(reason):
    raise ValueError(reason)

def stage(snapshot, sources, audit, candidates, today):
    if snapshot.get("publication_allowed") is not False:
        fail("source baseline must be an explicitly non-publishable archive")
    entries = {p["id"]: p for p in snapshot["catalog"]}
    if len(entries) != len(snapshot["catalog"]):
        fail("duplicate product catalog IDs")
    source_map = {p["id"]: p for p in sources["sources"]}
    audit_map = {p["id"]: p for p in audit["sources"]}
    if not isinstance(candidates.get("records"), list) or not candidates["records"]:
        fail("candidate rate records are empty or missing")
    start, end = japanese_period(today)
    period = start.isoformat() + "～" + end.isoformat()
    expected = defaultdict(set)
    for r in snapshot["rates"]:
        expected[r["product_id"]].add(dimension(r))
    actual = defaultdict(dict)
    errors = []
    for i, row in enumerate(candidates["records"]):
        prefix = f"records[{i}]"
        if not isinstance(row, dict):
            errors.append(f"{prefix}: not an object")
            continue
        missing = [k for k in REQUIRED_RECORD_FIELDS if k not in row or row[k] is None]
        if missing:
            errors.append(f"{prefix}: missing {missing}")
            continue
        pid = row["product_id"]
        if not isinstance(pid, str):
            errors.append(f"{prefix}: invalid product ID")
            continue
        if pid not in entries or pid not in source_map or pid not in audit_map:
            errors.append(f"{prefix}: product is not in all approved catalogs")
            continue
        source = source_map[pid]
        a = audit_map[pid]
        expected_url = source["url"]
        if row["source_url"] != expected_url or row["source_url"] != entries[pid]["rateurl"]:
            errors.append(f"{prefix}: source URL differs from v117 catalog and allowlist")
        parsed = urlsplit(row["source_url"])
        if parsed.scheme != "https" or not parsed.hostname:
            errors.append(f"{prefix}: source URL must use HTTPS")
        if (a.get("status") != "reachable" or not HEX.fullmatch(str(a.get("sha256", "")))
            or row["source_sha256"] != a.get("sha256")):
            errors.append(f"{prefix}: source evidence hash missing or mismatched")
        try:
            checked_date = dt.datetime.fromisoformat(a["checked_at_jst"])
            observed_date = dt.datetime.fromisoformat(row["source_observed_at"])
            if checked_date.tzinfo is None or observed_date.tzinfo is None:
                raise ValueError("Timezone required")
            if abs((checked_date - observed_date).total_seconds()) > 24*3600:
                errors.append(f"{prefix}: parser evidence is not from same audit day")
            if checked_date.astimezone(JST).date() < start:
                errors.append(f"{prefix}: source audit belongs to an older rate window")
        except (ValueError, TypeError, KeyError):
            errors.append(f"{prefix}: invalid audit/parser times")
        if row["period"] != period:
            errors.append(f"{prefix}: date period must equal {period}")
        if dimension(row) not in expected[pid]:
            errors.append(f"{prefix}: unknown currency/plan/term/age dimension")
        if dimension(row) in actual[pid]:
            errors.append(f"{prefix}: duplicated rate dimension")
        if row.get("extraction_method") not in ("official_html_table", "official_pdf_table"):
            errors.append(f"{prefix}: no source-specific table parser evidence")
        if not isinstance(row["source_locator"], str) or len(row["source_locator"].strip()) < 6:
            errors.append(f"{prefix}: missing exact source table position")
        try:
            numeric = float(row["value"])
            quoted = float(str(row["source_value_text"]).strip().replace("%", "").replace("％", "").replace(",", ""))
            if not (-10 <= numeric <= 30) or abs(numeric - quoted) > 0.00001:
                errors.append(f"{prefix}: rate differs from numeric text in source evidence")
        except (ValueError, TypeError):
            errors.append(f"{prefix}: invalid numeric rate")
        payout = row["payout"]
        baseline = next((old for old in snapshot["rates"] if old["product_id"] == pid and dimension(old) == dimension(row)), None)
        if baseline is not None and ((baseline.get("payout") is None) != (payout is None)):
            errors.append(f"{prefix}: payout schema differs from expected product condition")
        if payout is not None:
            if not isinstance(payout, dict) or set(payout) != {"male", "female"}:
                errors.append(f"{prefix}: male/female payout pair is required")
            elif not all(isinstance(payout[x], (int, float)) and 0 <= payout[x] <= 30 for x in ("male", "female")):
                errors.append(f"{prefix}: payout values invalid")
            # Both payout rates require independently traceable source locators.
            if not row.get("payout_source_locator_male") or not row.get("payout_source_locator_female"):
                errors.append(f"{prefix}: payout source locators missing")
        actual[pid][dimension(row)] = row
    for pid, rows in actual.items():
        missing = expected[pid] - set(rows)
        if missing:
            errors.append(f"{pid}: {len(missing)} expected rate condition(s) missing")
    if errors:
        fail("Candidate publication blocked:\n" + "\n".join("- "+e for e in errors))
    staged = {
        "schema_version": 1, "release_stage": "VALIDATED_NOT_PUBLISHED",
        "period": period,
        "checked_at_jst": dt.datetime.now(JST).isoformat(timespec="seconds"),
        "catalog_release": snapshot["release"],
        "source_products": sorted(actual),
        "records": [r for pid in sorted(actual) for r in actual[pid].values()],
        "note": "Machine checks passed. Independent source correctness and frontend tests are still required before deploying."
    }
    return staged

def main():
    root = pathlib.Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=pathlib.Path, default=root/"v117-rate-snapshot.json")
    parser.add_argument("--sources", type=pathlib.Path, default=root/"sources.json")
    parser.add_argument("--audit", type=pathlib.Path, default=root/"source-audit.json")
    parser.add_argument("--candidates", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, default=root/"staged-rates.json")
    parser.add_argument("--as-of", type=dt.date.fromisoformat)
    args = parser.parse_args()
    def read(p): return json.loads(p.read_text(encoding="utf-8"))
    day = args.as_of or dt.datetime.now(JST).date()
    result = stage(read(args.snapshot), read(args.sources), read(args.audit), read(args.candidates), day)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(f"Staged {len(result['records'])} rates across {len(result['source_products'])} products. NOT PUBLISHED.")

if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, json.JSONDecodeError) as e:
        print(f"BLOCKED: {e}", file=sys.stderr)
        sys.exit(1)
