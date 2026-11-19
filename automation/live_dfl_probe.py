#!/usr/bin/env python3
"""Required read-only integration of Daiichi Frontier live HTML against v117."""
import datetime as dt
import hashlib
import json
from pathlib import Path
from parse_dfl import URLS, extract, fetch, JST
from stage_rates import stage

ROOT=Path(__file__).resolve().parent
def main():
    now=dt.datetime.now(JST)
    snapshot=json.loads((ROOT/"v117-rate-snapshot.json").read_text())
    sources=json.loads((ROOT/"sources.json").read_text())
    for product in ("present","receive"):
        raw=fetch(product)
        candidates=extract(raw,product,now.date(),now.isoformat(timespec="seconds"))
        audit={"sources":[{"id":product, "status":"reachable",
              "sha256":hashlib.sha256(raw).hexdigest(),
              "checked_at_jst":now.isoformat(timespec="seconds")}]}
        staged=stage(snapshot,sources,audit,candidates,now.date())
        print("DFL LIVE SOURCE-TO-STAGE PASS:",product,
              len(staged["records"]),"rows",staged["period"])
        print("Representative rate:",staged["records"][0]["currency"],
              staged["records"][0]["value"],"percent")
    print("Test only: no publication or source file mutation")
if __name__=="__main__":
    main()
