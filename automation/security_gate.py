#!/usr/bin/env python3
"""Fail-closed guard: prohibit publishing a private or unreviewed mixed-purpose app.

Only metadata/category checks, never echo embedded document text. An all-clear
requires a maintained, reviewed allowlist of public material—not keyword
absence. This checker is deliberately conservative.
"""
import argparse
import json
import pathlib
import re
import sys
from build_preview import load_page

PRIVATE_CATEGORIES = ("agentdocs",)
PRIVATE_MARKERS = (
    "募集人用資料", "推奨商品一覧表", "社外秘", "社内限り",
    "募集人限り", "代理店限り", "顧客情報",
)
# Requiring private category removal is stronger than hiding a UI tab.
SRC_DOC = re.compile(r'<iframe\b[^>]*\bid="([^"]+)"[^>]*\bsrcdoc=', re.I|re.S)
EMBEDDED_BINARY = re.compile(r'data:(?:application/pdf|application/vnd[^;,]*|application/octet-stream);base64,', re.I)
UNREVIEWED_IMAGE = re.compile(r'data:image/(?:png|jpeg|webp|svg\+xml);base64,', re.I)

def inspect(page):
    reasons = []
    frames=set(SRC_DOC.findall(page))
    for category in PRIVATE_CATEGORIES:
        if category in frames or re.search(r'\bid="' + re.escape(category) + r'"',page):
            reasons.append("PRIVATE_SECTION_EMBEDDED")
    if any(marker in page for marker in PRIVATE_MARKERS):
        reasons.append("INTERNAL_DOCUMENT_MARKER_PRESENT")
    if EMBEDDED_BINARY.search(page):
        reasons.append("EMBEDDED_DOCUMENT_BINARY_UNREVIEWED")
    # Even ordinary images can include internal documents/scanned private data.
    if UNREVIEWED_IMAGE.search(page):
        reasons.append("EMBEDDED_IMAGE_REQUIRES_CONTENT_REVIEW")
    if not reasons:
        reasons.append("NO_PUBLIC_CONTENT_ALLOWLIST_APPROVAL")
    return {"publication_allowed":False,
            "review_status":"BLOCKED_PENDING_CONTENT_CLASSIFICATION",
            "finding_codes":sorted(set(reasons)),
            "note":"Automatic content scanning cannot prove there is no PII or confidential data. A per-asset review/allowlist is required.",
            "source_files":"v117/part*.js",
            "embedded_iframe_count":len(frames)}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--repo",type=pathlib.Path,default=pathlib.Path(__file__).resolve().parents[1])
    ap.add_argument("--report",type=pathlib.Path)
    args=ap.parse_args()
    report=inspect(load_page(args.repo))
    print("PUBLIC EXPORT SECURITY GATE: BLOCKED")
    for code in report["finding_codes"]:
        print(" -",code)
    if args.report:
        args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    sys.exit(1)

if __name__=="__main__":
    main()
