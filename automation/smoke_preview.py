#!/usr/bin/env python3
"""CI-only full-size package smoke test using SYNTHETIC rates.

Never saves demo values to the repository or the deployed site.
"""
import datetime as dt
import html
import json
import pathlib
import re
import tempfile

from build_preview import apply_rates, generate_preview, load_page, PRODUCTS, fnv1a_codepoints

ROOT = pathlib.Path(__file__).resolve().parents[1]
def main():
    page=load_page(ROOT)
    matches=list(PRODUCTS.finditer(page))
    if len(matches)!=1:
        raise ValueError(f"Found {len(matches)} embedded product lists, expected exactly one")
    products=json.loads(html.unescape(matches[0].group(1)))
    moon=next(p for p in products if p["id"]=="moon")
    rows=[]
    for i,original in enumerate([r for r in moon["rates"] if r["period"]=="2026-11-16～2026-11-30"]):
        row={k:original[k] for k in ("currency","label","term","lo","hi","payout")}
        row.update({"product_id":"moon","value":1.5+i,
                    "period":"2026-11-16～2026-11-30"})
        rows.append(row)
    if len(rows)!=2:
        raise ValueError("Test requires two current-window Moonshot baseline rows")
    stage={"release_stage":"VALIDATED_NOT_PUBLISHED","catalog_release":"v117",
           "period":"2026-11-16～2026-11-30",
           "checked_at_jst":"2026-11-19T10:00:00+09:00",
           "source_products":["moon"],"records":rows}
    new_page=apply_rates(page,stage)
    if page==new_page:
        raise ValueError("Preview did not change the rate rows")
    if len(new_page)<11_000_000:
        raise ValueError("Preview unexpectedly lost app content")
    with tempfile.TemporaryDirectory() as directory:
        out=pathlib.Path(directory)/"generated"
        stats=generate_preview(new_page,out)
        pieces=[]
        for i in range(stats["parts"]):
            raw=(out/"v118"/f"part{i:03d}.js").read_text(encoding="utf-8")
            match=re.fullmatch(r"window\.__insuranceV118\.push\((.*)\);",raw,re.DOTALL)
            if not match:
                raise ValueError("Bad generated JS part")
            pieces.append(json.loads(match.group(1)))
        restored="".join(pieces)
        if restored != new_page or fnv1a_codepoints(restored)!=int(stats["fnv1a"],16):
            raise ValueError("Round trip corruption in generated preview")
        if "<iframe" not in restored or 'id="single"' not in restored:
            raise ValueError("Preview lost comparison frames")
        print(f"Full-page preview round-trip OK: {stats['parts']} parts / {stats['utf16_length']} UTF-16 units")
        print("SYNTHETIC TEST RATES ONLY. All generated files destroyed after test.")

if __name__=="__main__":
    main()
