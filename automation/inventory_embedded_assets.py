#!/usr/bin/env python3
"""Metadata-only inventory of mixed-purpose v117 embedded materials.

Never output a document's text, an embedded image/PDF, email, phone number or
base64 bytes. Names are limited to known category IDs; everything else is
reported in aggregate counts and size bands.
"""
from collections import Counter
from html.parser import HTMLParser
import argparse
import json
import pathlib
import re

from build_preview import load_page

PRIVILEGED_IDS = {"agentdocs"}
SENSITIVE_WORDS = ("募集人用資料", "推奨商品一覧表", "社内限り", "募集人限り",
                   "社外秘", "取扱代理店用", "代理店限り")
EMBEDDED_URI = re.compile(r'data:([\w.+-]+/[\w.+-]+);base64,([A-Za-z0-9+/=\s]+)', re.I)
FRAME_START = re.compile(r'<iframe\b[^>]*\bsrcdoc="[^"]*"', re.I|re.S)
EMAIL = re.compile(r'(?<!\w)[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}(?!\w)')

class FrameMetadata(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.frames = []
    def handle_starttag(self, tag, attrs):
        if tag != "iframe":
            return
        attributes=dict(attrs)
        self.frames.append({
            "id": attributes.get("id", ""),
            "title": attributes.get("title", ""),
            "html": attributes.get("srcdoc", ""),
            "has_srcdoc": "srcdoc" in attributes,
        })

def inventory(page):
    parser=FrameMetadata()
    parser.feed(page)
    category_counts=Counter()
    known_privileged=[]
    frame_sizes=[]
    embedded_by_type=Counter()
    embedded_base64_bytes=0
    for frame in parser.frames:
        fid=frame["id"]
        category_counts["iframe_total"] += 1
        if frame["has_srcdoc"]:
            category_counts["iframe_inline_content"] += 1
            frame_sizes.append(len(frame["html"]))
        if fid in PRIVILEGED_IDS or any(x in frame["title"] for x in ("募集人", "社内")):
            known_privileged.append(fid if fid in PRIVILEGED_IDS else "internal_title_detected")
        # Check markup inside each frame, not merely outer page.
        text=frame["html"]
        for mime, encoded in EMBEDDED_URI.findall(text):
            embedded_by_type[mime.lower()]+=1
            embedded_base64_bytes+=len(encoded)
    for mime, encoded in EMBEDDED_URI.findall(page):
        # Outer page includes inner srcdoc; report outer scan as distinct metric
        # rather than combining it with per-frame counts.
        category_counts["outer_base64_uri_count"] += 1
    markers=[x for x in SENSITIVE_WORDS if x in page]
    return {
        "schema_version":1,
        "classification":"REQUIRES_MANUAL_ASSET_REVIEW",
        "publication_allowed":False,
        "source_release":"v117",
        "iframe_total":category_counts["iframe_total"],
        "iframe_inline_content":category_counts["iframe_inline_content"],
        "inline_frame_total_characters":sum(frame_sizes),
        "privileged_section_detected":bool(known_privileged),
        "internal_marker_categories_detected":len(markers),
        "embedded_mime_type_counts":dict(sorted(embedded_by_type.items())),
        "embedded_base64_character_count":embedded_base64_bytes,
        "embedded_outer_uris":category_counts["outer_base64_uri_count"],
        "privacy_note":"Metadata only. Cannot determine whether individual assets contain confidential information. Never publish this inventory as approval."
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--repo",type=pathlib.Path,default=pathlib.Path(__file__).resolve().parents[1])
    ap.add_argument("--output",type=pathlib.Path)
    args=ap.parse_args()
    result=inventory(load_page(args.repo))
    if args.output:
        args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if not result["privileged_section_detected"]:
        raise SystemExit("Expected private-content section not found; inventory schema may have changed")

if __name__=="__main__":
    main()
