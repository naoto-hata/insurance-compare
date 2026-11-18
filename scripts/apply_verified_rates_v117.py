#!/usr/bin/env python3
"""Publish independently verified rates to the checksum-verified v117 loader.
Writes the new parts and index in one Git commit (performed by workflow).
"""
import datetime as dt
import json
import re
import sys
from pathlib import Path
try:
    from scripts.apply_verified_rates import apply
    from scripts.validate_rates import validate
except ModuleNotFoundError:
    from apply_verified_rates import apply
    from validate_rates import validate

ROOT=Path("v117")
INDEX=Path("index.html")
PART_RE=re.compile(r'^window\.__insuranceV117\.push\((.*)\);\s*$',re.S)
SCRIPT_RE=re.compile(r'<script src="\./v117/part\d{3}\.js"></script>')

def checksum(s):
    h=2166136261
    for ch in s:
        h=((h ^ ord(ch))*16777619)&0xffffffff
    return h

def js_length(s):
    return sum(1 if ord(ch)<=65535 else 2 for ch in s)

def read():
    files=sorted(ROOT.glob("part[0-9][0-9][0-9].js"))
    if len(files)<5 or [p.name for p in files] != [f"part{i:03d}.js" for i in range(len(files))]:
        raise ValueError("v117 fragments missing or unexpected")
    pieces=[]
    for f in files:
        m=PART_RE.fullmatch(f.read_text(encoding="utf-8"))
        if not m:
            raise ValueError("Unexpected v117 part: "+f.name)
        value=json.loads(m.group(1))
        if not isinstance(value,str):
            raise ValueError("Bad v117 segment")
        pieces.append(value)
    source="".join(pieces)
    loader=INDEX.read_text(encoding="utf-8")
    if len(SCRIPT_RE.findall(loader))!=len(files):
        raise ValueError("Index count differs from staged fragments")
    length_match=re.search(r'page\.length!==(\d+)',loader)
    hash_match=re.search(r'hash!==0x([0-9a-f]{8})',loader)
    count_match=re.search(r'__insuranceV117\.length!==(\d+)',loader)
    if not length_match or not hash_match or not count_match:
        raise ValueError("Unsupported v117 loader")
    if int(length_match.group(1))!=js_length(source):
        raise ValueError("Public source length mismatch")
    if int(hash_match.group(1),16)!=checksum(source):
        raise ValueError("Public source checksum mismatch")
    if int(count_match.group(1))!=len(files):
        raise ValueError("Public source part count mismatch")
    if "第117版・一時払利率11月16日確認" not in source:
        raise ValueError("Missing v117 release marker")
    return source,files,loader

def write(source,files,loader):
    # One JS string segment per file, never split UTF-16 surrogate pairs.
    chunks=[source[i:i+360000] for i in range(0,len(source),360000)]
    if not chunks:
        raise ValueError("Empty output")
    revised=re.sub(r'page\.length!==\d+',f'page.length!=={js_length(source)}',loader,count=1)
    revised=re.sub(r'hash!==0x[0-9a-f]{8}',f'hash!==0x{checksum(source):08x}',revised,count=1)
    revised=re.sub(r'__insuranceV117\.length!==\d+',f'__insuranceV117.length!=={len(chunks)}',revised,count=1)
    before=SCRIPT_RE.findall(revised)
    if len(before)!=len(files):
        raise ValueError("Unexpected script layout")
    scripts="".join(f'<script src="./v117/part{i:03d}.js"></script>' for i in range(len(chunks)))
    # Keep the scripts before the final loader script
    revised=SCRIPT_RE.sub("",revised)
    anchor="<script>try{if("
    if revised.count(anchor)!=1:
        raise ValueError("Cannot locate bootstrap")
    revised=revised.replace(anchor,scripts+anchor,1)
    # Validate output prior to writing any files
    if len(SCRIPT_RE.findall(revised))!=len(chunks):
        raise ValueError("New loader part count mismatch")
    new_files=[ROOT/f"part{i:03d}.js" for i in range(len(chunks))]
    for f,part in zip(new_files,chunks):
        f.write_text("window.__insuranceV117.push("+json.dumps(part,ensure_ascii=False)+");",encoding="utf-8")
    for f in files:
        if f not in new_files:
            f.unlink()
    INDEX.write_text(revised,encoding="utf-8")
    print(f"Prepared {len(chunks)} fragments and atomic index update")

def main():
    payload=json.loads(Path("rates/approved.json").read_text(encoding="utf-8"))
    records=payload.get("rates")
    if not isinstance(records,list):
        raise SystemExit("Malformed approved-rate array")
    if not records:
        print("No approved records; public app unchanged")
        return
    errors=validate(records)
    if errors:
        raise SystemExit("\n".join(errors))
    old,files,loader=read()
    updated,count=apply(old,records)
    if not count:
        print("No currently effective approved rate changes")
        return
    write(updated,files,loader)
    print(f"Applied {count} condition(s), retaining prior periods")

if __name__=="__main__":
    main()
