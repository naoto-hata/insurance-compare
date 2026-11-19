#!/usr/bin/env python3
"""Build a *non-deploying* preview from verified staged rate records.

Do not call this with unverified candidates. Writes a new preview directory
containing its own index.html and v118 fragments. Never edits the original
index.html or v117 data.
"""
import argparse
import datetime as dt
import html
import json
import pathlib
import re
import shutil

from extract_single_rates import load_embedded_single, PART_RE

PRODUCTS = re.compile(r'const PRODUCTS=(\[.*?\]);', re.DOTALL)
MAX_PART = 360000
NEW_RELEASE = "v118"

def load_page(repo):
    chunks = []
    for i in range(32):
        raw = (repo/"v117"/f"part{i:03d}.js").read_text(encoding="utf-8")
        m = PART_RE.fullmatch(raw)
        if not m:
            raise ValueError(f"Corrupt fragment {i}")
        chunks.append(json.loads(m.group(1)))
    return "".join(chunks)

def apply_rates(page, staged):
    if staged.get("release_stage") != "VALIDATED_NOT_PUBLISHED" or staged.get("catalog_release") != "v117":
        raise ValueError("Only previously staged, v117-validated data can be previewed")
    found = list(PRODUCTS.finditer(page))
    if len(found) != 1:
        raise ValueError(f"Expected exactly one single-premium PRODUCTS array, found {len(found)}")
    match = found[0]
    before = json.loads(html.unescape(match.group(1)))
    by_id = {p["id"]: p for p in before}
    original_count = sum(len(p.get("rates", [])) for p in before)
    if len(by_id) != len(before) or len(by_id) != 13 or original_count != 219:
        raise ValueError("v117 product list drifted from independently audited baseline")
    updates = {}
    for record in staged["records"]:
        pid = record["product_id"]
        if pid not in by_id:
            raise ValueError(f"Unknown product {pid}")
        if record["period"] != staged["period"]:
            raise ValueError("Mixed source effective periods")
        rate = {key: record[key] for key in ("currency", "label", "term", "lo", "hi", "value", "period", "payout")}
        rate["extra"] = "公式利率データ取得・条件別照合済み。設計書の対象条件と一致するか契約前に再確認。"
        updates.setdefault(pid, []).append(rate)
    if sorted(updates) != sorted(staged.get("source_products", [])):
        raise ValueError("Staged product list mismatch")
    # A bundled rate is NOT automatically verified merely because its date is current.
    # Any current-window row not verified in this run must be held out.
    for pid, product in by_id.items():
        if pid in updates:
            continue
        original = product.get("rates", [])
        blocked = [r for r in original if r.get("period") == staged["period"]]
        if blocked:
            product["rates"] = [r for r in original if r.get("period") != staged["period"]]
            product["rateReview"] = "この適用期間の公式利率は今回未確認。旧版を現行値として表示しない。"
            product["missingReason"] = "今回の対象期間の利率は確認待ち。公式利率ページ・設計書で確認してください。"
    for pid, new_rows in updates.items():
        p = by_id[pid]
        old_rows = p["rates"]
        old_set = {(r["currency"],r["label"],r["term"],r["lo"],r["hi"]) for r in old_rows}
        new_set = {(r["currency"],r["label"],r["term"],r["lo"],r["hi"]) for r in new_rows}
        if new_set != old_set:
            raise ValueError(f"Rate dimensions for {pid} do not match historical catalog")
        p["rates"] = [r for r in old_rows if r["period"] != staged["period"]] + new_rows
        p["rateChecked"] = staged["checked_at_jst"][:10]
        p["rateReview"] = "自動抽出・一次資料条件照合済み（適用期間は利率欄を確認）。"
    encoded = html.escape(json.dumps(before, ensure_ascii=False, separators=(",", ":")), quote=True)
    result = page[:match.start(1)] + encoded + page[match.end(1):]
    # Critical: ensure only a single array changed and all unrelated iframe content remains untouched.
    if result[:match.start(1)] != page[:match.start(1)] or result.endswith(page[match.end(1):]) is False:
        raise ValueError("Unexpected non-rate modification")
    return result

def fnv1a_codepoints(page):
    hash_value = 2166136261
    for char in page:
        hash_value = ((hash_value ^ ord(char)) * 16777619) & 0xffffffff
    return hash_value

def generate_preview(page, directory):
    out = directory.resolve()
    if out.name in ("v117", "main") or out == pathlib.Path.cwd().resolve():
        raise ValueError("Unsafe output directory")
    if out.exists():
        raise ValueError("Preview output already exists; refuse overwrite")
    out.mkdir(parents=True)
    parts = [page[i:i+MAX_PART] for i in range(0,len(page),MAX_PART)]
    pieces = out/NEW_RELEASE
    pieces.mkdir()
    for i,chunk in enumerate(parts):
        (pieces/f"part{i:03d}.js").write_text("window.__insuranceV118.push("+json.dumps(chunk,ensure_ascii=False)+");",encoding="utf-8")
    utf16_len = len(page.encode("utf-16-le"))//2
    checksum = fnv1a_codepoints(page)
    scripts = "".join(f'<script src="./{NEW_RELEASE}/part{i:03d}.js"></script>' for i in range(len(parts)))
    loader = ('<!doctype html><html lang="ja"><head><meta charset="utf-8">'
              '<meta name="viewport" content="width=device-width,initial-scale=1">'
              '<title>保険比較アプリ 第118版（検証用プレビュー）</title></head><body>'
              '<p id="loading-message">第118版を検証用として読み込み中…</p>'
              '<script>window.__insuranceV118=[];</script>'+scripts+
              '<script>try{if(window.__insuranceV118.length!=='+str(len(parts))+
              ')throw Error("Missing part");let page=window.__insuranceV118.join("");'
              'if(page.length!=='+str(utf16_len)+')throw Error("Length mismatch");'
              'let h=2166136261>>>0;for(let i=0;i<page.length;i++){let cp=page.codePointAt(i);'
              'h=Math.imul(h^cp,16777619)>>>0;if(cp>65535)i++};'
              'if(h!==0x'+format(checksum,"08x")+')throw Error("Checksum mismatch");'
              'document.open();document.write(page);document.close()}catch(e){'
              'document.body.textContent="検証用プレビューを読み込めませんでした。";console.error(e)}</script>'
              '</body></html>')
    (out/"index.html").write_text(loader,encoding="utf-8")
    return {"parts":len(parts),"utf16_length":utf16_len,"fnv1a":format(checksum,"08x"),"total_chars":len(page)}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--repo",type=pathlib.Path,default=pathlib.Path(__file__).resolve().parents[1])
    ap.add_argument("--staged",type=pathlib.Path,required=True)
    ap.add_argument("--out",type=pathlib.Path,required=True)
    args=ap.parse_args()
    stage=json.loads(args.staged.read_text(encoding="utf-8"))
    page=apply_rates(load_page(args.repo),stage)
    stats=generate_preview(page,args.out)
    print("PREVIEW ONLY — NOT PUBLISHED:",stats)

if __name__=="__main__":
    main()
