#!/usr/bin/env python3
"""Deployment-package firewall for future public insurance rate pages.

Checks actual output directory, never just an input fixture. This does not
authorize publication; it prevents accidental copying of the mixed-purpose
v117 application or other files into a rates-only package.
"""
import argparse
import json
import pathlib
import re
import sys

from build_public_candidate_review import verify_safe_html

ALLOWED_PATHS={"index.html"}
FORBIDDEN_SUFFIXES={".pdf",".js",".map",".csv",".xlsx",".xls",".docx",".zip",".png",
                    ".webp",".jpg",".jpeg",".svg",".gif",".woff",".woff2"}
PRIVATE_MARKERS=("agentdocs","募集人用資料","社内限り","社外秘","推奨商品一覧表",
                 "募集人限り","customer_name","source_sha256","source_locator",
                 "source_url","base64,","v117/","v118/")

def check_package(path):
    root=pathlib.Path(path).resolve()
    if not root.is_dir():
        raise ValueError("Public package directory not found")
    if root.is_symlink():
        raise ValueError("Symlink output root forbidden")
    files=[]
    for entry in root.rglob("*"):
        if entry.is_symlink():
            raise ValueError("Symlink in public package forbidden")
        if entry.is_file():
            rel=entry.relative_to(root).as_posix()
            if rel not in ALLOWED_PATHS or entry.suffix.lower() in FORBIDDEN_SUFFIXES:
                raise ValueError("Non-allowlisted file in public rate package")
            files.append(rel)
    if sorted(files)!=sorted(ALLOWED_PATHS):
        raise ValueError("Missing or unexpected public rate package files")
    raw=(root/"index.html").read_bytes()
    if b"\x00" in raw or len(raw)>75_000:
        raise ValueError("Unexpected binary/large public HTML")
    content=raw.decode("utf-8",errors="strict")
    if any(x.casefold() in content.casefold() for x in PRIVATE_MARKERS):
        raise ValueError("Private material indicator in public HTML")
    verify_safe_html(content)
    return {"status":"STRUCTURALLY_SAFE_NOT_APPROVED",
            "publication_allowed":False,
            "files":files,"bytes":len(raw),
            "note":"No hidden assets in this package; separate authorization is required before external release."}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--directory",type=pathlib.Path,required=True)
    args=ap.parse_args()
    try:
        result=check_package(args.directory)
    except (ValueError,OSError,UnicodeError) as exc:
        print("PACKAGE SECURITY GATE BLOCKED:",type(exc).__name__,file=sys.stderr)
        return 1
    print(json.dumps(result,ensure_ascii=False))
    return 0

if __name__=="__main__":
    sys.exit(main())
