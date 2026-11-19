import copy
import tempfile
import pathlib
import unittest
from build_public_candidate_review import build_review_html, verify_safe_html

class PublicCandidateReviewTests(unittest.TestCase):
    def setUp(self):
        self.records=[]
        for pid,count in (("present",22),("receive",30),("moon",2)):
            for i in range(count):
                self.records.append({
                    "product_id":pid,"currency":"USD" if i%2 else "JPY",
                    "label":f"基本プラン{i}","term":"10年","lo":20,"hi":80,
                    "value":2.85,"period":"2026-11-16～2026-11-30",
                    "payout":{"male":3.1,"female":3.0} if pid=="receive" else None,
                    "source_url":"https://example.org/secret","secret":"CONFIDENTIAL_SHOULD_NOT_APPEAR",
                    "customer_name":"PRIVATE_CUSTOMER_XYZ"
                })
        self.staged={"release_stage":"VALIDATED_NOT_PUBLISHED",
                     "source_products":["present","receive","moon"],
                     "period":"2026-11-16～2026-11-30",
                     "records":self.records}
    def test_review_contains_only_approved_projection(self):
        page=build_review_html(self.staged)
        self.assertEqual(page.count("<tr>"),54)
        self.assertIn("publication_allowed: false",page)
        self.assertIn("3商品54条件",page)
        for forbidden in ("PRIVATE_CUSTOMER_XYZ","CONFIDENTIAL_SHOULD_NOT_APPEAR",
                          "https://example.org/secret","<iframe","<script","data:image","<img"):
            self.assertNotIn(forbidden,page)
    def test_unknown_product_blocked(self):
        self.records[0]["product_id"]="private-secret-product"
        with self.assertRaises(ValueError):build_review_html(self.staged)
    def test_incomplete_records_blocked(self):
        self.records.pop()
        with self.assertRaises(ValueError):build_review_html(self.staged)
    def test_markup_in_plan_blocked(self):
        self.records[0]["label"]='<img src="https://evil.example">'
        with self.assertRaises(ValueError):build_review_html(self.staged)
    def test_internal_marker_in_plan_blocked(self):
        self.records[0]["label"]="募集人用資料"
        with self.assertRaises(ValueError):build_review_html(self.staged)
    def test_script_tag_in_page_blocked(self):
        with self.assertRaises(ValueError):verify_safe_html("<script>bad()</script>"+"<tr>"*54+"publication_allowed: false")
    def test_explicit_wrong_approval_blocked(self):
        stage={**self.staged,"release_stage":"UNVERIFIED"}
        with self.assertRaises(ValueError):build_review_html(stage)
    def test_invalid_rate_blocked(self):
        self.records[0]["value"]=999
        with self.assertRaises(ValueError):build_review_html(self.staged)
if __name__=="__main__":
    unittest.main()
