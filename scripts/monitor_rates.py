#!/usr/bin/env python3
"""Official-rate source monitor. Never treats downloaded text as a verified rate."""
import datetime as dt
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

SOURCES = [
    ("メットライフ｜サニーガーデン", "https://www.metlife.co.jp/lf1/ahp805/08.html"),
    ("メットライフ｜ビーウィズユー米ドル", "https://www.metlife.co.jp/lf1/ahp770/08.html"),
    ("メットライフ｜ビーウィズユー円", "https://www.metlife.co.jp/lf1/ahp771/08.html"),
    ("第一フロンティア｜プレミアプレゼント5", "https://www.d-frontier-life.co.jp/products/index_hendo_shushin_choice_20_6.html?agency=227&product=224"),
    ("第一フロンティア｜プレミアレシーブ2", "https://www.d-frontier-life.co.jp/products/index_recurrining_payment_shushin_23.html?agency=132&product=204"),
    ("マニュライフ｜未来を楽しむ", "https://www.manulife.co.jp/ja/individual/rates/tanoshimusyushin/int.html"),
    ("マニュライフ｜未来につなげる", "https://www.manulife.co.jp/ja/individual/rates/miraisyushinv2-1/ln-baseint.html"),
    ("FWD｜円建一時払変額年金", "https://customer.fwdlife.co.jp/seimei/rate/AccumulatedInterestRateDistributionRate.html"),
    ("オリックス｜ムーンショット", "https://www.orixlife.co.jp/fx/whole-life/accumulation-interest-rate"),
    ("ジブラルタ｜一時払終身", "https://www.gib-life.co.jp/st/intro/products/kyotsu/rate/tatsuka_syushin_23/fxrate/"),
    ("ソニー｜一時払終身", "https://www.sonylife.co.jp/rate/accumulation_interest_rate/"),
]
JST = dt.timezone(dt.timedelta(hours=9))
now = dt.datetime.now(JST)
period_start = 1 if now.day < 16 else 16
period_end = 15 if period_start == 1 else (dt.date(now.year + (now.month == 12), now.month % 12 + 1, 1) - dt.timedelta(days=1)).day
period = f"{now.year}-{now.month:02d}-{period_start:02d}"
rows = []
for name, url in SOURCES:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; InsuranceRateSourceMonitor/1.0)"})
        with urllib.request.urlopen(req, timeout=22) as response:
            kind = response.headers.get("Content-Type", "")
            body = response.read(1200000)
            status = response.status
        decoded = body.decode("utf-8", errors="replace")
        # This is a connectivity check, NOT a validation of the new rates.
        result = "取得可・数値未照合" if status == 200 and body else "空の応答"
        if "pdf" in kind.lower() or body[:4] == b"%PDF":
            result = "PDF取得可・数値未照合"
        if len(decoded) < 150 and not body.startswith(b"%PDF"):
            result = "短い応答・要確認"
        rows.append({"name": name, "url": url, "status": result, "http": status})
    except Exception as exc:
        rows.append({"name": name, "url": url, "status": "取得失敗・要確認", "error": str(exc)[:160]})
report = [f"# 一時払利率・公式情報監視 {period_start}～{period_end}日", "",
          f"実行日時: {now.strftime('%Y-%m-%d %H:%M JST')}", "",
          "**重要:** 公式URLへの到達確認のみ。新利率・通貨・期間・年齢・性別・定期支払率は未照合です。",
          "確認できない利率を自動掲載しません。公開アプリの利率データはこの処理では変更しません。", "",
          "| 商品 | 監視結果 | 公式URL |", "|---|---|---|"]
for r in rows:
    report.append(f"| {r['name']} | {r['status']} | [開く]({r['url']}) |")
report += ["", "数値の自動取得・突合・公開は各社ごとの検証済みパーサー実装後に有効化します。"]
output = "\n".join(report)
Path("rate-monitor-report.md").write_text(output, encoding="utf-8")
Path("rate-monitor-report.json").write_text(json.dumps({"period":period,"checked_at":now.isoformat(),"results":rows},ensure_ascii=False,indent=2),encoding="utf-8")
if os.environ.get("GITHUB_STEP_SUMMARY"):
    with open(os.environ["GITHUB_STEP_SUMMARY"],"a",encoding="utf-8") as f: f.write(output+"\n")
print(output)
