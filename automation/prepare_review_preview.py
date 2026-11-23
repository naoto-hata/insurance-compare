#!/usr/bin/env python3
"""Build an isolated preview from three exact official HTTP responses.

The preview may be uploaded as an Actions artifact for *review only*.
Neither public Pages files nor the default branch are modified.
"""
import datetime as dt
import hashlib
import json
import os
import pathlib
import urllib.request

from parse_dfl import fetch as fetch_dfl, extract as extract_dfl, URLS as DFL_URLS
from parse_moonshot import SOURCE_URL, parse_official_html
from stage_rates import stage
from build_preview import load_page, apply_rates, generate_preview

ROOT=pathlib.Path(__file__).resolve().parent
JST=dt.timezone(dt.timedelta(hours=9))

def prepare(output_root, today=None):
    now=dt.datetime.now(JST)
    day=today or now.date()
    if day != now.date():
        raise ValueError("Refusing non-current period for live preview")
    snapshot=json.loads((ROOT/"v117-rate-snapshot.json").read_text(encoding="utf-8"))
    sources=json.loads((ROOT/"sources.json").read_text(encoding="utf-8"))
    expected={"present","receive","moon"}
    source_by_id={x["id"]:x for x in sources["sources"]}
    if not expected.issubset(source_by_id):
        raise ValueError("Missing insurer URL registration")
    records=[]
    audit=[]
    for pid in ("present","receive","moon"):
        url=DFL_URLS[pid] if pid!="moon" else SOURCE_URL
        if source_by_id[pid]["url"]!=url:
            raise ValueError(f"Source URL drift for {pid}")
        if pid=="moon":
            req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"text/html"})
            with urllib.request.urlopen(req,timeout=30) as response:
                if response.geturl()!=url:
                    raise ValueError("Moonshot source redirected")
                raw=response.read(2_000_001)
            if len(raw)>2_000_000:
                raise ValueError("Moonshot official HTML size limit")
            candidates=parse_official_html(raw,day,now.isoformat(timespec="seconds"))
        else:
            raw=fetch_dfl(pid)
            candidates=extract_dfl(raw,pid,day,now.isoformat(timespec="seconds"))
        records.extend(candidates["records"])
        audit.append({"id":pid,"status":"reachable","sha256":hashlib.sha256(raw).hexdigest(),
                      "checked_at_jst":now.isoformat(timespec="seconds")})
    staged=stage(snapshot,sources,{"sources":audit},{"records":records},day)
    if len(staged["records"])!=54:
        raise ValueError("Incomplete 54-cell rate batch")
    out=pathlib.Path(output_root).resolve()
    if out.exists():
        raise ValueError("Preview destination already exists")
    if out.is_relative_to(ROOT.parent.resolve()):
        raise ValueError("Never write preview into the tracked repository")
    packaged=apply_rates(load_page(ROOT.parent),staged)
    stats=generate_preview(packaged,out)
    manifest={"as_of_jst":day.isoformat(),"effective_period":staged["period"],
              "release_stage":"REVIEW_ONLY_NOT_DEPLOYED",
              "source_products":{"present":22,"receive":30,"moon":2},
              "preview_parts":stats["parts"],"utf16_length":stats["utf16_length"],
              "fnv1a":stats["fnv1a"],"publication_allowed":False,
              "caution":"Prototype rate preview. Other 10 products remain unverified; do not use as a live quote."}
    (out/"REVIEW_MANIFEST.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("REVIEW-ONLY PREVIEW PACKAGE:", json.dumps(manifest,ensure_ascii=False))
    return manifest

if __name__=="__main__":
    runner_temp=os.environ.get("RUNNER_TEMP")
    if not runner_temp:
        raise SystemExit("RUNNER_TEMP is required; refusing local/untracked output")
    prepare(pathlib.Path(runner_temp)/"insurance-review-preview")
