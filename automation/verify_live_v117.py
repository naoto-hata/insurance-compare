#!/usr/bin/env python3
"""Read-only verification that the actual public GitHub Pages rate view matches main.

Only fetch the fixed known HTTPS rate-only document. No secret/private v117
assets are requested and no HTML payload is logged. Deploy propagation gets
a short retry window on push; scheduled checks detect persistent mismatch.
"""
import hashlib
import pathlib
import sys
import time
import urllib.request

HERE=pathlib.Path(__file__).resolve().parents[1]
PAGE_URL="https://naoto-hata.github.io/insurance-compare/rates-current.html"
LIMIT=40_000

def verify_http_response(payload, local):
    if len(payload)>LIMIT or not payload.startswith(b"<!doctype html>"):
        raise ValueError("Unexpected public rate-only page payload")
    if hashlib.sha256(payload).digest()!=hashlib.sha256(local).digest():
        raise ValueError("Published rate page differs from verified main file")
    return True

def verify_live(retries=3,delay_seconds=8):
    expected=(HERE/"rates-current.html").read_bytes()
    last_error=None
    for attempt in range(retries):
        try:
            request=urllib.request.Request(PAGE_URL,headers={
                "User-Agent":"InsuranceComparePublicPageIntegrity/1.0",
                "Cache-Control":"no-cache",
            })
            with urllib.request.urlopen(request,timeout=15) as response:
                if response.geturl().split("?")[0] != PAGE_URL:
                    raise ValueError("Public page redirected unexpectedly")
                if response.status != 200:
                    raise ValueError("Public page did not return HTTP 200")
                actual=response.read(LIMIT+1)
            verify_http_response(actual,expected)
            print("PASS: Live rate-only GitHub Pages matches checked-out main file.")
            return True
        except (OSError,ValueError) as e:
            last_error=type(e).__name__
            if attempt+1<retries:
                time.sleep(delay_seconds)
    raise ValueError("Public page integrity or accessibility check failed: "+str(last_error))

if __name__=="__main__":
    try:
        verify_live()
    except ValueError:
        print("PUBLIC PAGE INTEGRITY CHECK FAILED; no page content printed.",file=sys.stderr)
        sys.exit(1)
