#!/usr/bin/env python3
"""Read (but never rewrite) the single-premium product/rate data in v117.

The app stores its HTML as 32 JSON-encoded JavaScript fragments, with the
single-premium comparison embedded inside an iframe srcdoc attribute.
This exporter creates a small independent data snapshot without binary artwork.
Its contents are *archived observations*, not current verified insurer quotes.
"""
import argparse
import html
import json
import pathlib
import re
import sys

PART_RE = re.compile(r'^window\.__insuranceV117\.push\((.*)\);\s*$', re.DOTALL)
IFRAME_RE = re.compile(r'<iframe\s+id="single"\b[^>]*?\bsrcdoc="(.*?)"\s+title=', re.DOTALL)
PRODUCTS_RE = re.compile(r'\bconst\s+PRODUCTS\s*=\s*(\[.*?\])\s*;', re.DOTALL)
DATE_RE = re.compile(r'^(\d{4}-\d{2}-\d{2})～(\d{4}-\d{2}-\d{2})$')

def load_embedded_single(repo):
    parts = sorted((repo / "v117").glob("part[0-9][0-9][0-9].js"))
    if len(parts) != 32 or [p.name for p in parts] != [f"part{i:03}.js" for i in range(32)]:
        raise ValueError("v117 fragments incomplete; expected exactly part000.js through part031.js")
    chunks = []
    for part in parts:
        raw = part.read_text(encoding="utf-8")
        m = PART_RE.fullmatch(raw)
        if not m:
            raise ValueError(f"Invalid JS fragment: {part.name}")
        chunks.append(json.loads(m.group(1)))
    page = "".join(chunks)
    # v117 wrapper pins the exact length; reject partial or changed releases.
    utf16_length = len(page.encode("utf-16-le")) // 2
    if utf16_length != 11251223:
        raise ValueError(f"Unexpected v117 UTF-16 length {utf16_length}")
    match = IFRAME_RE.search(page)
    if not match:
        raise ValueError("Single-premium iframe srcdoc not found")
    inner = html.unescape(match.group(1))
    products_match = PRODUCTS_RE.search(inner)
    if not products_match:
        raise ValueError("PRODUCTS array not found in single-premium iframe")
    try:
        products = json.loads(products_match.group(1))
    except json.JSONDecodeError as exc:
        raise ValueError(f"PRODUCTS not JSON-serializable: {exc}") from exc
    if not isinstance(products, list) or not products:
        raise ValueError("No products in single-premium iframe")
    return products

def extract(products):
    rows = []
    catalog = []
    keys = set()
    for product in products:
        if not isinstance(product, dict) or not product.get("id"):
            raise ValueError("Product missing stable ID")
        meta = {k: product.get(k) for k in ("id", "company", "name", "kind", "url", "rateurl", "checked", "rateChecked", "missingReason")}
        catalog.append(meta)
        for rate in product.get("rates", []):
            if not isinstance(rate, dict) or rate.get("value") is None:
                continue
            period = rate.get("period") or ""
            if not DATE_RE.fullmatch(period):
                raise ValueError(f"Invalid or missing rate period: {product['id']} {period}")
            row = {
                "product_id": product["id"], "company": product.get("company"),
                "product": product.get("name"), "currency": rate.get("currency"),
                "label": rate.get("label"), "term": rate.get("term"),
                "age_min": rate.get("lo"), "age_max": rate.get("hi"),
                "value": rate.get("value"), "payout": rate.get("payout"),
                "period": period, "extra": rate.get("extra"),
                "source_url": product.get("rateurl") or product.get("url"),
                "source_checked": product.get("rateChecked") or product.get("checked"),
                "verification_status": "ARCHIVE_ONLY_NOT_CURRENT_VERIFIED"
            }
            key = tuple(str(row[k]) for k in ("product_id", "currency", "label", "term", "age_min", "age_max", "period"))
            if key in keys:
                raise ValueError(f"Duplicate rate dimensions: {key}")
            keys.add(key)
            rows.append(row)
    if not rows:
        raise ValueError("No rate rows extracted")
    return {"schema_version": 1, "release": "v117",
            "publication_allowed": False,
            "warning": "Historical snapshot extracted from the embedded app; never treat as current verified insurer rates.",
            "catalog": catalog, "rates": rows}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=pathlib.Path, default=pathlib.Path(__file__).resolve().parents[1])
    ap.add_argument("--out", type=pathlib.Path, default=pathlib.Path(__file__).resolve().parent / "v117-rate-snapshot.json")
    args = ap.parse_args()
    data = extract(load_embedded_single(args.repo))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f'Exported {len(data["catalog"])} products and {len(data["rates"])} archived rate conditions to {args.out}')
    print("Publication forbidden: insurer source verification not done")

if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, json.JSONDecodeError) as error:
        print(f"BLOCKED: {error}", file=sys.stderr)
        sys.exit(1)
