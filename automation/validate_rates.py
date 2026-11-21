#!/usr/bin/env python3
"""Strict validator for insurer-sourced interest-rate records.

No record is considered publishable unless source, effective dates and every
required product dimension are explicit and independently populated.
"""
import argparse
import datetime as dt
import json
import pathlib
import sys
from urllib.parse import urlsplit

REQUIRED = ("company", "product", "rate_type", "currency", "term_years",
            "plan", "premium_band", "sex", "age_band", "effective_from",
            "effective_through", "rate_percent", "source_url",
            "source_published_at", "source_locator", "retrieved_at")
KEY_FIELDS = ("company", "product", "rate_type", "currency", "term_years",
              "plan", "premium_band", "sex", "age_band")
ALLOWED_CURRENCIES = {"JPY", "USD", "AUD", "EUR", "NZD"}
ALLOWED_RATE_TYPES = {"積立利率", "予定利率", "定期支払率"}
ALLOWED_SEX = {"男性", "女性", "共通", "該当なし"}
NULL_EQUIVALENTS = {"", "-", "不明", "確認待ち", "未確認", "null", "none"}

def japanese_period(day):
    start = day.replace(day=1 if day.day <= 15 else 16)
    if day.day <= 15:
        end = day.replace(day=15)
    else:
        next_month = (day.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
        end = next_month - dt.timedelta(days=1)
    return start, end

def validate(document, today=None):
    today = today or dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date()
    errors = []
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        return ["schema_version must equal 1"]
    if not isinstance(document.get("records"), list) or not document["records"]:
        return ["records must be a nonempty array"]
    expected_start, expected_end = japanese_period(today)
    seen = set()
    for i, row in enumerate(document["records"]):
        prefix = f"records[{i}]"
        if not isinstance(row, dict):
            errors.append(f"{prefix}: must be an object")
            continue
        missing = [key for key in REQUIRED if
                   key not in row or row[key] is None or
                   (isinstance(row[key], str) and row[key].strip().lower() in NULL_EQUIVALENTS)]
        if missing:
            errors.append(f"{prefix}: missing or unconfirmed {', '.join(missing)}")
            continue
        key = tuple(str(row[f]) for f in KEY_FIELDS)
        if key in seen:
            errors.append(f"{prefix}: duplicate product and rate condition")
        seen.add(key)
        if row["currency"] not in ALLOWED_CURRENCIES:
            errors.append(f"{prefix}: unsupported currency")
        if row["rate_type"] not in ALLOWED_RATE_TYPES:
            errors.append(f"{prefix}: unsupported rate type")
        if row["sex"] not in ALLOWED_SEX:
            errors.append(f"{prefix}: unsupported sex dimension")
        try:
            years = int(row["term_years"])
            if not 0 <= years <= 100:
                raise ValueError()
        except (ValueError, TypeError):
            errors.append(f"{prefix}: invalid term_years")
        try:
            rate = float(row["rate_percent"])
            if not -10 <= rate <= 30 or not str(row["rate_percent"]).strip():
                raise ValueError()
        except (ValueError, TypeError):
            errors.append(f"{prefix}: invalid rate_percent")
        try:
            start = dt.date.fromisoformat(row["effective_from"])
            end = dt.date.fromisoformat(row["effective_through"])
            published = dt.date.fromisoformat(row["source_published_at"][:10])
            retrieved = dt.datetime.fromisoformat(row["retrieved_at"].replace("Z", "+00:00"))
            if (start, end) != (expected_start, expected_end):
                errors.append(f"{prefix}: effective window must match current Japanese half-month")
            if published > today or retrieved.date() > today:
                errors.append(f"{prefix}: source timestamps in the future")
            if published < start - dt.timedelta(days=31):
                errors.append(f"{prefix}: old source publication date; manual source mapping required")
        except (ValueError, TypeError):
            errors.append(f"{prefix}: invalid source or effective dates")
        parsed = urlsplit(row["source_url"])
        if parsed.scheme != "https" or not parsed.hostname or not (
            parsed.hostname.endswith(".co.jp") or parsed.hostname.endswith(".jp")):
            errors.append(f"{prefix}: source must be an HTTPS Japanese official site")
        # Publication requires an allowlist-controlled source catalog, not merely a matching hostname.
        if row.get("source_verified") is not True or row.get("source_type") not in ("official_html", "official_pdf"):
            errors.append(f"{prefix}: official source evidence not verified")
        if not isinstance(row["source_locator"], str) or len(row["source_locator"]) < 4:
            errors.append(f"{prefix}: missing exact official source locator")
    return errors

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=pathlib.Path)
    parser.add_argument("--as-of", type=dt.date.fromisoformat)
    args = parser.parse_args()
    document = json.loads(args.path.read_text(encoding="utf-8"))
    errors = validate(document, args.as_of)
    if errors:
        print("BLOCKED: rate publication not permitted")
        print("\n".join(f"- {e}" for e in errors))
        sys.exit(1)
    print(f"VALIDATED: {len(document['records'])} records (individual row checks only)")
    print("WARNING: product completeness and site rendering checks must also pass before publication")

if __name__ == "__main__":
    main()
