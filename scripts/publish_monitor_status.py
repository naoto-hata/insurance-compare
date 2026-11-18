#!/usr/bin/env python3
"""Publish connectivity status only (never publish rates or raw downloaded pages)."""
import datetime as dt
import json
from pathlib import Path

source = json.loads(Path("rate-monitor-report.json").read_text(encoding="utf-8"))
catalog = json.loads(Path("rates/catalog.json").read_text(encoding="utf-8"))
ids = {p["name"]: p["id"] for p in catalog["products"]}
allowed = {"取得可・数値未照合", "PDF取得可・数値未照合", "空の応答",
           "短い応答・要確認", "取得失敗・要確認"}
results = []
for item in source.get("results", []):
    if item.get("name") not in ids:
        raise ValueError("Unknown catalog item")
    if item.get("status") not in allowed:
        raise ValueError("Unknown monitoring result")
    digest = item.get("content_sha256")
    if digest is not None and (not isinstance(digest, str) or len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest)):
        raise ValueError("Invalid source checksum")
    results.append({"product_id": ids[item["name"]], "status": item["status"],
                    "content_sha256": digest, "content_changed": bool(item.get("content_changed", False))})
if len(results) != len(catalog["products"]) or len({r["product_id"] for r in results}) != len(results):
    raise ValueError("Missing or duplicate products in report")
when = dt.datetime.fromisoformat(source["checked_at"])
if when.tzinfo is None:
    raise ValueError("Monitoring timestamp requires timezone")
stamp = dt.datetime.now(dt.timezone.utc)
if abs((stamp - when.astimezone(dt.timezone.utc)).total_seconds()) > 7200:
    raise ValueError("Monitoring report is stale")
output = {"schema_version": 1, "checked_at": when.isoformat(),
          "rate_data_updated": False, "rate_verification": "not_performed",
          "monitoring_results": results}
Path("rates/status.json").write_text(json.dumps(output, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
print("Wrote rate-source monitoring status (no interest rate figures).")
