import datetime as dt
import html
import json
import pathlib
import tempfile
import unittest
from build_preview import apply_rates, generate_preview, fnv1a_codepoints

class PreviewBuilderTests(unittest.TestCase):
    def setUp(self):
        self.products=[]
        for i in range(13):
            count = 2 if i == 0 else (206 if i == 1 else 1)
            rates=[{"currency":"JPY","label":f"プラン{j}","term":"10年",
                    "lo":0,"hi":90,"value":1.0,"payout":None,
                    "period":"2026-10-16～2026-10-31"} for j in range(count)]
            self.products.append({"id":"moon" if i==0 else f"other{i}","rates":rates})
        self.assertEqual(sum(len(p["rates"]) for p in self.products),219)
        self.page='<script>const PRODUCTS='+html.escape(json.dumps(self.products,ensure_ascii=False),quote=True)+';</script>'
        self.records=[{"product_id":"moon","currency":"JPY","label":f"プラン{j}",
                       "term":"10年","lo":0,"hi":90,"value":2.5+j,
                       "payout":None,"period":"2026-11-16～2026-11-30"} for j in range(2)]
        self.staged={"release_stage":"VALIDATED_NOT_PUBLISHED","catalog_release":"v117",
                     "period":"2026-11-16～2026-11-30","checked_at_jst":"2026-11-19T10:00:00+09:00",
                     "source_products":["moon"],"records":self.records}
    def test_applies_only_updated_product(self):
        updated=apply_rates(self.page,self.staged)
        products=json.loads(html.unescape(updated.split("const PRODUCTS=")[1].split(";</script>")[0]))
        self.assertEqual(len(products[0]["rates"]),4)
        self.assertEqual(products[0]["rates"][-1]["value"],3.5)
        self.assertEqual(products[1],self.products[1])
    def test_unverified_current_window_rate_suppressed(self):
        # A different product carries an embedded current-period number,
        # but there is no corresponding fresh, official source verification.
        self.products[1]["rates"][0]["period"]="2026-11-16～2026-11-30"
        page='<script>const PRODUCTS='+html.escape(json.dumps(self.products,ensure_ascii=False),quote=True)+';</script>'
        updated=apply_rates(page,self.staged)
        products=json.loads(html.unescape(updated.split("const PRODUCTS=")[1].split(";</script>")[0]))
        unverified=products[1]
        self.assertFalse(any(r["period"]==self.staged["period"] for r in unverified["rates"]))
        self.assertIn("確認待ち",unverified["missingReason"])
        self.assertEqual(len(unverified["rates"]),205)
        self.assertEqual(len(products[0]["rates"]),4)
    def test_no_change_when_other_products_have_only_history(self):
        updated=apply_rates(self.page,self.staged)
        products=json.loads(html.unescape(updated.split("const PRODUCTS=")[1].split(";</script>")[0]))
        self.assertEqual(products[2],self.products[2])
    def test_stale_release_claims_replaced_in_review_only(self):
        old_heading="一時払利率チェック：2026年11月16日／5商品67条件を更新"
        old_note=("2026年11月16日確認：プレミアプレゼント5・プレミアレシーブ2・FWD・"
                  "ムーンショット・ソニー生命の5商品67条件を11月16～30日の公式利率に更新。")
        page=self.page+old_heading+old_note
        updated=apply_rates(page,self.staged)
        self.assertNotIn(old_heading,updated)
        self.assertNotIn(old_note,updated)
        self.assertIn("1商品2条件を照合・その他は確認待ち",updated)
        self.assertIn("今回照合していない利率は現行値として表示せず",updated)
    def test_wrong_release_blocked(self):
        stage={**self.staged,"catalog_release":"v999"}
        with self.assertRaises(ValueError):
            apply_rates(self.page,stage)
    def test_incomplete_product_blocked(self):
        stage={**self.staged,"records":self.records[:1]}
        with self.assertRaisesRegex(ValueError,"dimensions"):
            apply_rates(self.page,stage)
    def test_new_directory_build_and_checksum(self):
        with tempfile.TemporaryDirectory() as folder:
            output=pathlib.Path(folder)/"preview"
            page=apply_rates(self.page,self.staged)
            stats=generate_preview(page,output)
            self.assertEqual(stats["fnv1a"],format(fnv1a_codepoints(page),"08x"))
            self.assertTrue((output/"index.html").exists())
            self.assertEqual(len(list((output/"v118").glob("part*.js"))),stats["parts"])
    def test_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError,"already exists"):
                generate_preview(self.page,pathlib.Path(folder))
if __name__=="__main__":
    unittest.main()
