#!/usr/bin/env python3
"""Official-site data -> 54 rate rows -> full-size nonpublic preview.

No data is committed, deployed, or persisted. All files are generated in a
temporary directory and deleted after this integration test.
"""
import datetime as dt
import hashlib
import html
import json
import pathlib
import tempfile
from build_preview import PRODUCTS, apply_rates, load_page, generate_preview
from parse_dfl import extract as extract_dfl, fetch as fetch_dfl, JST
from parse_moonshot import parse_official_html, SOURCE_URL
from stage_rates import stage
from build_public_candidate_review import build_review_html, verify_safe_html
from check_public_package import check_package
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent
REPO = ROOT.parent

def main():
    now = dt.datetime.now(JST)
    snapshot = json.loads((ROOT / "v117-rate-snapshot.json").read_text(encoding="utf-8"))
    sources = json.loads((ROOT / "sources.json").read_text(encoding="utf-8"))
    records=[]
    aud=[]
    for pid in ("present","receive"):
        raw = fetch_dfl(pid)
        candidates = extract_dfl(raw,pid,now.date(),now.isoformat(timespec="seconds"))
        records.extend(candidates["records"])
        aud.append({"id":pid,"status":"reachable","sha256":hashlib.sha256(raw).hexdigest(),
                    "checked_at_jst":now.isoformat(timespec="seconds")})
    req=urllib.request.Request(SOURCE_URL,headers={"User-Agent":"Mozilla/5.0","Accept":"text/html"})
    with urllib.request.urlopen(req,timeout=30) as response:
        if response.geturl()!=SOURCE_URL:
            raise ValueError("Moonshot redirected unexpectedly")
        raw=response.read(2_000_001)
        if len(raw)>2_000_000:
            raise ValueError("Moonshot page exceeds source limit")
    moon=parse_official_html(raw,now.date(),now.isoformat(timespec="seconds"))
    records.extend(moon["records"])
    aud.append({"id":"moon","status":"reachable","sha256":hashlib.sha256(raw).hexdigest(),
                "checked_at_jst":now.isoformat(timespec="seconds")})
    staged=stage(snapshot,sources,{"sources":aud},{"records":records},now.date())
    assert len(staged["records"]) == 54, "Expected 22 + 30 + 2"
    safe_review=build_review_html(staged)
    assert verify_safe_html(safe_review)
    assert len(safe_review.encode("utf-8")) < 75_000
    with tempfile.TemporaryDirectory() as candidate_root:
        public_dir=pathlib.Path(candidate_root)
        (public_dir/"index.html").write_text(safe_review,encoding="utf-8")
        security=check_package(public_dir)
        assert security["publication_allowed"] is False
        assert security["files"]==["index.html"]
    print("PUBLIC-CANDIDATE-ONLY HTML BUILT AND DIRECTORY-GATED (never deployed):",len(safe_review.encode("utf-8")),"bytes")
    original=load_page(REPO)
    updated=apply_rates(original,staged)
    lists=list(PRODUCTS.finditer(updated))
    assert len(lists)==1
    modified=json.loads(html.unescape(lists[0].group(1)))
    original_products=json.loads(html.unescape(list(PRODUCTS.finditer(original))[0].group(1)))
    changed={"present","receive","moon"}
    for new,old in zip(modified,original_products):
        assert new["id"]==old["id"]
        if new["id"] not in changed:
            old_current=[r for r in old["rates"] if r["period"]==staged["period"]]
            new_current=[r for r in new["rates"] if r["period"]==staged["period"]]
            assert not new_current, "Unverified current-period rate was left visible"
            if not old_current:
                assert new==old, "Unrelated product with no current rates changed"
            else:
                assert len(new["rates"])==len(old["rates"])-len(old_current), "Unexpected historical rate change"
                assert new.get("missingReason"), "Missing explicit review warning"
        else:
            current=[r for r in new["rates"] if r["period"]==staged["period"]]
            expected={"present":22,"receive":30,"moon":2}[new["id"]]
            assert len(current)==expected
    with tempfile.TemporaryDirectory() as folder:
        result=generate_preview(updated,pathlib.Path(folder)/"preview")
        assert result["parts"] >= 1
        print("LIVE SOURCES -> STAGED 54 -> FULL-PAGE PREVIEW: PASS")
        print("Source-verified conditions:",{p:len([r for r in records if r["product_id"]==p]) for p in changed})
        print("Preview:",result["parts"],"parts; checksum",result["fnv1a"])
        print("All files removed automatically. No public site modification.")

if __name__=="__main__":
    main()
