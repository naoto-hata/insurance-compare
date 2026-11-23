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

def classify_response(status, body, content_type):
    """Classify reachability only; large pages are NOT 'missing' rate sources."""
    if status != 200:
        return "HTTP_STATUS_REVIEW_REQUIRED"
    if not body:
        return "EMPTY_SOURCE_REVIEW_REQUIRED"
    if body.startswith(b"%PDF") or "application/pdf" in content_type.lower():
        return "OFFICIAL_PDF_ACCESSIBLE_NOT_PARSED"
    if len(body) > MAX_BYTES:
        return "LARGE_PAGE_ACCESSIBLE_NOT_PARSED"
    return "REACHABLE_RATE_VALUES_UNVERIFIED"

def check():
    catalog=json.loads(SOURCES.read_text(encoding="utf-8"))
    selection=analyze_sources(catalog)
    opener=urllib.request.build_opener(RestrictedRedirect())
    statuses={}
    for source in selection:
        code="ACCESS_NEEDS_REVIEW"
        try:
            req=urllib.request.Request(source["url"],headers={
                "User-Agent":"InsuranceCompareRateSourceHealth/1.0",
                "Accept":"text/html,application/pdf",
            })
            with opener.open(req,timeout=TIMEOUT) as response:
                p=urlsplit(response.geturl())
                if p.scheme!="https" or p.hostname not in ALLOWED_HOSTS:
                    raise ValueError("Unapproved final host")
                sample=response.read(MAX_BYTES+1)
                code=classify_response(response.status,sample,response.headers.get("Content-Type",""))
        except urllib.error.HTTPError as exc:
            code="HTTP_"+str(exc.code)+"_ACCESS_REVIEW_REQUIRED"
        except (OSError,urllib.error.URLError,ValueError,TimeoutError):
            code="ACCESS_NEEDS_REVIEW"
        # This emits only static product IDs and finite status codes;
        # not URLs, HTML, source document excerpts or exception strings.
        statuses[code]=statuses.get(code,0)+1
        print("Remaining-product",source["id"],code)
    print("READ ONLY: ten source checks",json.dumps(statuses,sort_keys=True))
    print("NO NUMERIC RATE VERIFICATION; no assets, contact data or downloaded pages retained.")

if __name__=="__main__":
    check()
