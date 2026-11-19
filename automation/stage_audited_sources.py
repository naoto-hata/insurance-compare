#!/usr/bin/env python3
"""Stage 54 official rates from *exact audited source bytes*, without publishing.

Intended for scheduled GitHub Actions after audit_sources.py. Any missing or
unverified source blocks this staged batch. No previous-period fallback.
"""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
from parse_dfl import extract as dfl_extract
from parse_moonshot import parse_official_html
from stage_rates import stage
from validate_rates import japanese_period

JST=dt.timezone(dt.timedelta(hours=9))
ROOT=Path(__file__).resolve().parent
CACHE=Path(os.environ.get("RATE_SOURCE_CACHE","/tmp/insurance-rate-source-cache"))
PRODUCTS=("present","receive","moon")

def main():
    now=dt.datetime.now(JST)
    snapshot=json.loads((ROOT/"v117-rate-snapshot.json").read_text(encoding="utf-8"))
    sources=json.loads((ROOT/"sources.json").read_text(encoding="utf-8"))
    audit=json.loads((ROOT/"source-audit.json").read_text(encoding="utf-8"))
    audited={r["id"]:r for r in audit["sources"]}
    if not all(pid in audited for pid in PRODUCTS):
        raise ValueError("Missing audited insurer product")
    candidates=[]
    for pid in PRODUCTS:
        info=audited[pid]
        if info.get("status")!="reachable":
            raise ValueError(f"{pid}: official page not accessible")
        data=(CACHE/(pid+".html")).read_bytes()
        if hashlib.sha256(data).hexdigest()!=info.get("sha256"):
            raise ValueError(f"{pid}: audited bytes differ from parsed bytes")
        parsed=(parse_official_html(data,now.date(),info["checked_at_jst"]) if pid=="moon"
                else dfl_extract(data,pid,now.date(),info["checked_at_jst"]))
        candidates.extend(parsed["records"])
    validated=stage(snapshot,sources,audit,{"records":candidates},now.date())
    if len(validated["records"])!=54:
        raise ValueError("Expected 54 complete rate conditions")
    # Stored under GitHub Actions runner temp path ONLY; never committed.
    output=Path(os.environ.get("RATE_STAGE_OUTPUT","/tmp/insurance-rate-staged.json"))
    if output.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError("Refusing to stage unapproved rates in tracked repo directory")
    output.write_text(json.dumps(validated,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("STAGED ONLY: 54 official rate conditions; NOT PUBLICLY RELEASED",output)

if __name__=="__main__":
    main()
