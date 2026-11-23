#!/usr/bin/env python3
"""Read-only live insurer rates -> MINIMAL safe review package -> DELETE.

No private v117 source HTML or embedded asset is loaded. The archive is read
only as a small metadata-only rate dimension snapshot for staging, and it is
not copied into the generated HTML. Nothing is uploaded or deployed.
"""
import datetime as dt
import hashlib
import json
import pathlib
import tempfile
import urllib.request

from parse_dfl import fetch as fetch_dfl, extract as extract_dfl
from parse_moonshot import parse_official_html, SOURCE_URL
from stage_rates import stage
from build_public_candidate_review import build_review_html
from check_public_package import check_package

ROOT=pathlib.Path(__file__).resolve().parent
JST=dt.timezone(dt.timedelta(hours=9))

def run():
    now=dt.datetime.now(JST)
    baseline=json.loads((ROOT/"v117-rate-snapshot.json").read_text(encoding="utf-8"))
    source_catalog=json.loads((ROOT/"sources.json").read_text(encoding="utf-8"))
    official_rows=[]
    evidence=[]
    for pid in ("present","receive","moon"):
        if pid=="moon":
            req=urllib.request.Request(SOURCE_URL,headers={"User-Agent":"Mozilla/5.0","Accept":"text/html"})
            with urllib.request.urlopen(req,timeout=30) as response:
                if response.geturl()!=SOURCE_URL:
                    raise ValueError("Moonshot official source redirect")
                raw=response.read(2_000_001)
            if len(raw)>2_000_000:raise ValueError("Moonshot HTML size limit")
            candidates=parse_official_html(raw,now.date(),now.isoformat(timespec="seconds"))
        else:
            raw=fetch_dfl(pid)
            candidates=extract_dfl(raw,pid,now.date(),now.isoformat(timespec="seconds"))
        official_rows.extend(candidates["records"])
        evidence.append({"id":pid,"status":"reachable","sha256":hashlib.sha256(raw).hexdigest(),
                         "checked_at_jst":now.isoformat(timespec="seconds")})
    valid=stage(baseline,source_catalog,{"sources":evidence},{"records":official_rows},now.date())
    page=build_review_html(valid)
    with tempfile.TemporaryDirectory(prefix="safe-rates-") as tmp:
        out=pathlib.Path(tmp)
        (out/"index.html").write_text(page,encoding="utf-8")
        result=check_package(out)
        if result["publication_allowed"] is not False or result["files"]!=["index.html"]:
            raise ValueError("Safe build's release status changed unexpectedly")
        print("SAFE RATE-ONLY LIVE INTEGRATION: PASS")
        print("Verified cells:",len(valid["records"]),"total HTML bytes:",result["bytes"])
        print("Explicit release permission:",result["publication_allowed"])
        print("No source app pages loaded; temporary review removed; no upload or deploy.")

if __name__=="__main__":
    run()
