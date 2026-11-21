#!/usr/bin/env python3
"""Build a strictly limited, NON-PUBLIC, rates-only HTML review page.

No source application, iframe, image, JS, hyperlinks, source URLs, PDF, customer
information, or internal notes are copied to the page. The projection is
explicitly unapproved for publication. All dynamic values are HTML-escaped.
"""
import argparse
import datetime as dt
import html
import json
import pathlib
import re
import sys
from public_rate_projection import project, EXPECTED

ALLOWED_CURRENCIES = {"JPY": "円", "USD": "米ドル", "AUD": "豪ドル"}
# Deny any executable, linked, or embedded content. This is *not* equivalent
# to business/legal approval for public redistribution.
PROHIBITED_HTML = re.compile(
    r"<(?:script|iframe|frame|object|embed|img|svg|canvas|video|audio|"
    r"form|input|link|a)\b|(?:src|href)\s*=|data:[a-z/+-]+;base64,",
    re.IGNORECASE,
)
PRIVATE_MARKERS = (
    "募集人用資料", "社外秘", "社内限り", "推奨商品一覧表",
    "代理店限り", "募集人限り", "顧客情報", "customer_name",
    "source_sha256", "source_locator", "source_url",
)

def safe_text(value):
    if isinstance(value, (dict, list, tuple)) or value is None:
        raise ValueError("Unexpected structured/text null field in public-candidate row")
    s = str(value)
    if len(s) > 90 or any(ord(c) < 32 for c in s):
        raise ValueError("Unusually long or control-character public field")
    if any(x in s for x in ("<", ">", "&", '"', "'", "{", "}")):
        raise ValueError("Unsafe punctuation in public-candidate field")
    if any(keyword in s for keyword in PRIVATE_MARKERS):
        raise ValueError("Internal or private marker in projected text")
    return html.escape(s, quote=True)

def verify_safe_html(document):
    if PROHIBITED_HTML.search(document):
        raise ValueError("Executable, linked or embedded content forbidden")
    if any(marker in document for marker in PRIVATE_MARKERS):
        raise ValueError("Confidentiality marker in HTML")
    if document.count("<tr><td>") != 54:
        raise ValueError("Expected 54 rate rows in review table")
    if len(document.encode("utf-8")) > 75_000:
        raise ValueError("Unexpectedly large review page")
    if "publication_allowed" not in document or "false" not in document:
        raise ValueError("Review-only marker missing")
    return True

def build_review_html(staged):
    data = project(staged)
    period = safe_text(data["effective_period"])
    rows = []
    for r in data["records"]:
        if r["currency"] not in ALLOWED_CURRENCIES:
            raise ValueError("Unsupported rate currency")
        if not isinstance(r["value"], (int, float)) or isinstance(r["value"], bool):
            raise ValueError("Invalid numeric rate")
        if not (0 <= r["value"] <= 20):
            raise ValueError("Out-of-range rate")
        lo, hi = r["lo"], r["hi"]
        if not all(isinstance(x,int) and not isinstance(x,bool) for x in (lo,hi)) or not 0 <= lo <= hi <= 120:
            raise ValueError("Invalid age range")
        sex = r["payout"]
        if sex is not None:
            if not isinstance(sex, dict) or set(sex) != {"male","female"}:
                raise ValueError("Malformed payout fields")
            if any(not isinstance(sex[k],(int,float)) or isinstance(sex[k],bool) or not 0<=sex[k]<=20 for k in ("male","female")):
                raise ValueError("Invalid payout rate")
            payout = f'{sex["male"]:.2f}% / {sex["female"]:.2f}%'
        else:
            payout = "—"
        values = (
            safe_text(r["company"]), safe_text(r["product"]),
            safe_text(ALLOWED_CURRENCIES[r["currency"]]),
            safe_text(r["label"]), safe_text(r["term"]),
            f"{lo}〜{hi}歳", f'{r["value"]:.2f}%', payout,
        )
        rows.append("<tr>" + "".join("<td>"+x+"</td>" for x in values) + "</tr>")
    expected = sum(EXPECTED.values())
    if len(rows) != expected:
        raise ValueError("Incomplete public-candidate review")
    page = """<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>一時払保険・利率確認用（非公開）</title>
<style>
body{font-family:system-ui,-apple-system,sans-serif;margin:24px;color:#202c3a;line-height:1.5}
main{max-width:1200px;margin:auto}h1{font-size:1.5rem}
.notice{border:1px solid #bbb;padding:12px;border-radius:6px}
.tablewrap{overflow-x:auto}
table{width:100%;border-collapse:collapse;min-width:760px}
th,td{padding:9px;border-bottom:1px solid #ddd;text-align:left;font-size:.9rem}
thead{background:#f1f3f5}td:nth-child(7){font-weight:700}
</style></head><body><main>
<h1>一時払保険・積立利率の確認用一覧</h1>
<p class="notice">社内の公開可否審査前の検証ページ。お客様への提示・外部共有・本番公開には使用しないこと。<strong>publication_allowed: false</strong></p>
<p>適用期間：PERIOD　／公式ページから取得した3商品54条件のみ掲載。その他の商品は確認待ち。</p>
<div class="tablewrap"><table><thead><tr><th>保険会社</th><th>商品</th><th>通貨</th><th>プラン</th><th>保証期間</th><th>契約年齢</th><th>積立利率</th><th>定期支払率 男性 / 女性</th></tr></thead>
<tbody>ROWS</tbody></table></div>
<p>利率と定期支払率は異なる指標。加入可否・費用・解約条件・実際の設計内容は保険会社の最新資料で確認。</p>
</main></body></html>""".replace("PERIOD", period).replace("ROWS", "".join(rows))
    verify_safe_html(page)
    return page

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--staged", type=pathlib.Path, required=True)
    ap.add_argument("--out", type=pathlib.Path, required=True)
    args=ap.parse_args()
    destination=args.out.resolve()
    # Never write a public-ready HTML into the checked-out repository.
    root=pathlib.Path(__file__).resolve().parents[1]
    if destination.is_relative_to(root):
        raise ValueError("Review output cannot be written into public repository")
    if destination.exists():
        raise ValueError("Refusing to overwrite existing review output")
    staged=json.loads(args.staged.read_text(encoding="utf-8"))
    page=build_review_html(staged)
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(page,encoding="utf-8")
    print("NON-PUBLIC RATE-ONLY REVIEW OK, 54 rows, no embedded assets, JS or links")

if __name__=="__main__":
    try:
        main()
    except (ValueError,OSError,KeyError,json.JSONDecodeError) as error:
        print("RATE-ONLY REVIEW BLOCKED:",type(error).__name__,file=sys.stderr)
        sys.exit(1)
