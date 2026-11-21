#!/usr/bin/env python3
"""Read-only public official URL health checks for remaining 10 rate products.

Never download/store agency paperwork, print source HTML, commit files, or
assume an HTTP 200 means rates have been validated. This checker is only a
triage aid for building product-specific parsers later.
"""
import json
import pathlib
import ssl
import urllib.error
import urllib.request
from urllib.parse import urlsplit

ROOT=pathlib.Path(__file__).resolve().parents[1]
SOURCES=ROOT/"automation/sources.json"
SUPPORTED={"present","receive","moon"}
MAX_BYTES=128_000
TIMEOUT=10
ALLOWED_HOSTS={
    "www.metlife.co.jp","www2.axa.co.jp","www.manulife.co.jp",
    "www.medicarelife.com","customer.fwdlife.co.jp",
    "customer2.fwdlife.co.jp","www.gib-life.co.jp",
    "www.sonylife.co.jp",
}
class RestrictedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        p=urlsplit(newurl)
        if p.scheme!="https" or p.hostname not in ALLOWED_HOSTS:
            raise ValueError("Unapproved insurer source redirect")
        return super().redirect_request(request,fp,code,msg,headers,newurl)

def analyze_sources(catalog):
    sources=catalog["sources"]
    selected=[x for x in sources if x["id"] not in SUPPORTED]
    if len(sources)!=13 or len(selected)!=10 or len({x["id"] for x in sources})!=13:
        raise ValueError("Expected exact original 13-product catalog")
    for s in selected:
        p=urlsplit(s["url"])
        if p.scheme!="https" or p.hostname not in ALLOWED_HOSTS or p.username or p.password:
            raise ValueError("Source not on official insurer host allowlist")
    return selected

def check():
    catalog=json.loads(SOURCES.read_text(encoding="utf-8"))
    selection=analyze_sources(catalog)
    opener=urllib.request.build_opener(RestrictedRedirect())
    reachable=0
    for source in selection:
        status="REVIEW_REQUIRED"
        try:
            req=urllib.request.Request(source["url"],headers={
                "User-Agent":"InsuranceCompareRateSourceHealth/1.0",
                "Accept":"text/html",
            })
            with opener.open(req,timeout=TIMEOUT) as response:
                p=urlsplit(response.geturl())
                if p.scheme!="https" or p.hostname not in ALLOWED_HOSTS:
                    raise ValueError("Unapproved final host")
                # Read only a bounded prefix; never log its contents or save it.
                sample=response.read(MAX_BYTES+1)
                if response.status==200 and len(sample)<=MAX_BYTES:
                    status="REACHABLE_NOT_VERIFIED"
                    reachable+=1
                elif len(sample)>MAX_BYTES:
                    status="TOO_LARGE_TO_INSPECT"
        except (OSError,urllib.error.URLError,ValueError,TimeoutError):
            status="ACCESS_NEEDS_REVIEW"
        print("Remaining-product",source["id"],status)
    print("READ ONLY: reachable sources",reachable,"of 10; no rate values validated, no artifacts produced.")

if __name__=="__main__":
    check()
